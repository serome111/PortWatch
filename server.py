#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PortWatch Web Panel – FastAPI server
 - Recolecta conexiones con psutil
 - Calcula score por proceso/destino con heurísticas
 - Expone API JSON y sirve el index.html
"""
import time
import socket
import ipaddress
import subprocess
import os
import re
import sys
from collections import defaultdict, deque
from typing import Dict, List, Tuple

import psutil
import numpy as np
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response
from datetime import datetime
import signal


SENSITIVE_PORTS = {22, 23, 25, 445, 3389, 5900}
# Hints por puertos característicos
MINING_PORTS = {3333, 4444}
TOR_PORTS = set(range(9001, 9031))  # 9001–9030
TMP_HINTS = ("/tmp", "/private/tmp", "/var/tmp", "/dev/shm")


# Historial de timestamps por (pid, dst)
HIST = defaultdict(lambda: deque(maxlen=200))
WINDOW_SECONDS = 120
SIGN_CACHE: Dict[str, Dict] = {}
OWN_PID = os.getpid()
PROTECT_SELF = os.getenv("PW_PROTECT_SELF", "1") != "0"


app = FastAPI(title="PortWatch Web Panel")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/")
def root():
    # Sirve el HTML desde archivo local
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


def _now():
    return time.time()


def _is_macos() -> bool:
    try:
        return sys.platform == "darwin"
    except Exception:
        return False


def _is_self_or_ancestor(pid: int) -> bool:
    """True si el PID es este servidor o algún ancestro suyo (para protegernos)."""
    try:
        if pid == OWN_PID:
            return True
        me = psutil.Process(OWN_PID)
        for pp in me.parents():
            if pp.pid == pid:
                return True
        return False
    except Exception:
        return False


def _beacon_flag(pid: int, dst_key: str, now_ts: float) -> bool:
    # Heurística: >=4 hits en 60s y stddev(intervalos) < 2s
    ts = [t for t in HIST[(pid, dst_key)] if now_ts - t <= 60]
    if len(ts) < 4:
        return False
    ts = sorted(ts)
    intervals = np.diff(ts)
    if len(intervals) == 0:
        return False
    return float(np.std(intervals)) < 2.0


def _is_public_ip(ip: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip)
        return not (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
        )
    except ValueError:
        return False


def _score_row(row: Dict) -> Tuple[float, str, List[str]]:
    """Devuelve (score[0-10], nivel: bajo/medio/alto, razones)."""
    score = 0.0
    reasons: List[str] = []

    # Puertos sensibles
    if row.get("dport") in SENSITIVE_PORTS:
        score += 3.0
        reasons.append("Puerto sensible")

    # Hints: minería (Stratum) y Tor
    dport = row.get("dport")
    if isinstance(dport, int) and dport in MINING_PORTS:
        score += 2.0
        reasons.append("Puerto típico de minería (3333/4444)")
    if isinstance(dport, int) and dport in TOR_PORTS:
        score += 1.5
        reasons.append("Puerto típico de Tor (9001-9030)")

    # Ejecución desde /tmp o similares
    exe = (row.get("exe") or "").lower()
    if any(h in exe for h in TMP_HINTS):
        score += 3.0
        reasons.append("Ejecutable en carpeta temporal")

    # Conexión hacia IP pública
    rhost = (row.get("raddr") or "").split(":")[0]
    if _is_public_ip(rhost):
        score += 1.0
        reasons.append("Conecta a Internet (IP pública)")

    # Edad del binario: reciente + salida a Internet
    exe_path = row.get("exe") or ""
    exe_recent = bool(row.get("exe_recent"))
    if exe_path and not exe_recent:
        try:
            mtime = os.path.getmtime(exe_path)
            exe_recent = (_now() - float(mtime)) <= (72*3600)
        except Exception:
            exe_recent = False
    if exe_recent and _is_public_ip(rhost):
        score += 1.0
        reasons.append("Binario reciente con salida")

    # Beaconing
    if row.get("beacon"):
        score += 2.5
        reasons.append("Patrón repetitivo de conexión")

    # Demasiados destinos distintos por proceso
    if row.get("unique_dsts", 0) >= 10:
        score += 1.5
        reasons.append("Muchos destinos distintos")
    elif row.get("unique_dsts", 0) >= 5:
        score += 0.8

    # Firma de código / ubicación
    exe = (row.get("exe") or "")
    signed = bool(row.get("signed"))
    apple = bool(row.get("apple"))
    quarantine = bool(row.get("quarantine"))

    if not signed:
        score += 2.0
        reasons.append("Aplicación sin firma")
    elif apple:
        score -= 1.5
        reasons.append("Aplicación de Apple")

    if quarantine:
        score += 1.0
        reasons.append("Marcado como descargado recientemente")

    exe_l = exe.lower()
    if exe_l.startswith("/system/") or exe_l.startswith("/usr/bin") or exe_l.startswith("/usr/libexec"):
        if apple:
            score -= 0.5
    if ("/users/" in exe_l and ("/downloads" in exe_l or "/library/" in exe_l)) and _is_public_ip((row.get("raddr") or "").split(":")[0]):
        score += 0.5
        reasons.append("Ejecutable en carpeta de usuario")

    score = min(score, 10.0)
    score = max(score, 0.0)
    level = "bajo"
    if score >= 7.0:
        level = "alto"
    elif score >= 4.0:
        level = "medio"
    return score, level, reasons


def _service_name(port: int | None) -> str:
    if not isinstance(port, int):
        return ""
    # Etiquetas para puertos especiales
    if port in MINING_PORTS:
        return "mining-stratum"
    if port in TOR_PORTS:
        return "tor"
    for proto in ("tcp", "udp"):
        try:
            return socket.getservbyport(port, proto)
        except Exception:
            continue
    return ""


def _proc_info_cache() -> Dict[int, Dict]:
    out: Dict[int, Dict] = {}
    for p in psutil.process_iter(attrs=["pid", "name", "username", "exe"]):
        info = p.info
        out[info["pid"]] = {
            "pid": info.get("pid"),
            "proc": info.get("name") or "?",
            "user": info.get("username") or "?",
            "exe": info.get("exe") or "",
        }
        
    return out


def _fmt_addr(addr) -> str:
    try:
        if not addr:
            return ""
        if isinstance(addr, tuple) and len(addr) >= 2:
            return f"{addr[0]}:{addr[1]}"
        return str(addr)
    except Exception:
        return ""


def _ts_iso(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).isoformat(sep=" ")
    except Exception:
        return str(ts)


def _parse_codesign_output(text: str) -> Dict:
    # Heurística simple: si ejecuta sin error => firmado
    signed = "Signature=adhoc" not in text and ("Authority=" in text or "CodeDirectory v=" in text)
    apple = "Authority=Apple" in text
    # Cadena de autoridad para inspección manual
    authorities = [line.split("=", 1)[1].strip() for line in text.splitlines() if line.strip().startswith("Authority=")]
    return {"signed": signed, "apple": apple, "authorities": authorities}


def _sign_info_for_exe(exe: str) -> Dict:
    if not exe or not os.path.isfile(exe):
        return {"signed": False, "apple": False, "authorities": [], "notarized": False, "quarantine": False}

    # Cache
    if exe in SIGN_CACHE:
        return SIGN_CACHE[exe]

    result = {"signed": False, "apple": False, "authorities": [], "notarized": False, "quarantine": False}
    try:
        cs = subprocess.run(["/usr/bin/codesign", "-dv", "--verbose=4", exe], capture_output=True, text=True)
        text = cs.stdout + cs.stderr
        parsed = _parse_codesign_output(text)
        result.update(parsed)
    except Exception:
        pass

    try:
        sp = subprocess.run(["/usr/sbin/spctl", "-a", "-vv", exe], capture_output=True, text=True)
        o = sp.stdout + sp.stderr
        # accepted = firma válida por Gatekeeper; notarized aparece en source
        result["notarized"] = ("accepted" in o.lower()) and ("notarized" in o.lower() or "source=apple" in o.lower() or "developer id" in o.lower())
    except Exception:
        pass

    # Quarantine xattr
    try:
        x = subprocess.run(["/usr/bin/xattr", "-p", "com.apple.quarantine", exe], capture_output=True, text=True)
        result["quarantine"] = x.returncode == 0 and bool((x.stdout or x.stderr).strip())
    except Exception:
        result["quarantine"] = False

    SIGN_CACHE[exe] = result
    return result


def _collect_connections_psutil(established_only: bool = False) -> List[Dict]:
    now_ts = _now()
    rows: List[Dict] = []

    proc_map = _proc_info_cache()

    try:
        conns = psutil.net_connections(kind="inet")
    except Exception:
        conns = []

    # Filtramos solo conexiones con raddr (remotas)
    filtered = [c for c in conns if getattr(c, "raddr", None)]
    if established_only:
        try:
            filtered = [c for c in filtered if getattr(c, "status", "") == psutil.CONN_ESTABLISHED]
        except Exception:
            filtered = [c for c in filtered if str(getattr(c, "status", "")) == "ESTABLISHED"]
    filtered.sort(key=lambda c: (getattr(c, "status", "") != psutil.CONN_ESTABLISHED,))

    # Prepara conteo de destinos únicos por pid
    unique_by_pid: Dict[int, set] = defaultdict(set)

    # Primera pasada: construir filas básicas y beacons
    for c in filtered:
        pid = getattr(c, "pid", None) or -1
        laddr = _fmt_addr(getattr(c, "laddr", None))
        raddr = _fmt_addr(getattr(c, "raddr", None))
        dport = None
        try:
            if getattr(c, "raddr", None):
                dport = c.raddr.port
        except Exception:
            dport = None

        dst_key = raddr
        if pid != -1 and dst_key:
            HIST[(pid, dst_key)].append(now_ts)
        beacon = _beacon_flag(pid, dst_key, now_ts) if pid != -1 and dst_key else False

        pinfo = proc_map.get(pid, {"pid": pid, "proc": "?", "user": "?", "exe": ""})
        exe = pinfo.get("exe") or ""
        sign = _sign_info_for_exe(exe) if exe else {"signed": False, "apple": False, "notarized": False, "quarantine": False, "authorities": []}
        # Edad del binario (reciente en últimas 72h)
        exe_recent = False
        if exe:
            try:
                exe_recent = (now_ts - float(os.path.getmtime(exe))) <= (72*3600)
            except Exception:
                exe_recent = False
        row = {
            "pid": pid,
            "proc": pinfo.get("proc", "?"),
            "user": pinfo.get("user", "?"),
            "exe": exe,
            "laddr": laddr or "",
            "raddr": raddr or "",
            "dport": dport,
            "service": _service_name(dport),
            "status": getattr(c, "status", ""),
            "beacon": bool(beacon),
            "unique_dsts": 0,
            "signed": bool(sign.get("signed")),
            "apple": bool(sign.get("apple")),
            "notarized": bool(sign.get("notarized")),
            "quarantine": bool(sign.get("quarantine")),
            "authorities": sign.get("authorities", []),
            "exe_recent": bool(exe_recent),
        }
        # Rellenar conteo por pid
        if raddr:
            unique_by_pid[pid].add(raddr.split(":")[0])

        rows.append(row)

    # Segunda pasada: completar unique_dsts y score/level
    for r in rows:
        r["unique_dsts"] = len(unique_by_pid.get(r["pid"], set()))
        score, level, reasons = _score_row(r)
        r["score"] = score
        r["level"] = level
        r["reasons"] = reasons

    # Ordenar por score desc y luego por beacon
    rows.sort(key=lambda x: (-(x.get("score", 0)), not x.get("beacon", False)))
    return rows


def _collect_connections_lsof(established_only: bool = False) -> List[Dict]:
    """Fallback para macOS usando lsof cuando psutil no tiene permisos/visibilidad."""
    rows: List[Dict] = []
    try:
        proc = subprocess.run(["lsof", "-i", "-P", "-n", "-F", "pcnTu"], capture_output=True, text=True)
        if proc.returncode != 0:
            return []
        now_ts = _now()
        current: Dict[str, object] = {"pid": -1, "proc": "?", "user": "?", "status": "", "proto": ""}
        unique_by_pid: Dict[int, set] = defaultdict(set)
        for raw in proc.stdout.splitlines():
            if not raw:
                continue
            tag, val = raw[0], raw[1:]
            if tag == "p":
                try:
                    current["pid"] = int(val)
                except Exception:
                    current["pid"] = -1
            elif tag == "c":
                current["proc"] = val
            elif tag == "u":
                current["user"] = val
            elif tag == "T":
                # Ej: ST=ESTABLISHED o P=TCP
                if val.startswith("ST="):
                    current["status"] = val[3:]
                elif val.startswith("P="):
                    current["proto"] = val[2:]
            elif tag == "n":
                name = val  # Ej: 192.168.1.5:52344->151.101.1.69:443
                laddr, raddr, dport = "", "", None
                if "->" in name:
                    left, right = name.split("->", 1)
                    laddr, raddr = left, right
                    if ":" in right:
                        try:
                            dport = int(right.rsplit(":", 1)[1])
                        except Exception:
                            dport = None
                else:
                    laddr = name
                if established_only and str(current.get("status", "")) != "ESTABLISHED":
                    continue

                pid = int(current.get("pid") or -1)
                try:
                    exe = psutil.Process(pid).exe() if pid != -1 else ""
                except Exception:
                    exe = ""
                sign = _sign_info_for_exe(exe) if exe else {"signed": False, "apple": False, "notarized": False, "quarantine": False, "authorities": []}
                # Edad del binario (reciente en últimas 72h)
                exe_recent = False
                if exe:
                    try:
                        exe_recent = (now_ts - float(os.path.getmtime(exe))) <= (72*3600)
                    except Exception:
                        exe_recent = False
                row = {
                    "pid": pid,
                    "proc": str(current.get("proc") or "?"),
                    "user": str(current.get("user") or "?"),
                    "exe": exe or "",
                    "laddr": laddr,
                    "raddr": raddr,
                    "dport": dport,
                    "service": _service_name(dport),
                    "status": str(current.get("status") or ""),
                    "beacon": False,
                    "unique_dsts": 0,
                    "signed": bool(sign.get("signed")),
                    "apple": bool(sign.get("apple")),
                    "notarized": bool(sign.get("notarized")),
                    "quarantine": bool(sign.get("quarantine")),
                    "authorities": sign.get("authorities", []),
                    "exe_recent": bool(exe_recent),
                }
                dst_key = row["raddr"]
                if pid != -1 and dst_key:
                    HIST[(pid, dst_key)].append(now_ts)
                    row["beacon"] = _beacon_flag(pid, dst_key, now_ts)
                    unique_by_pid[pid].add(dst_key.split(":")[0])
                rows.append(row)

        for r in rows:
            r["unique_dsts"] = len(unique_by_pid.get(r["pid"], set()))
            score, level, reasons = _score_row(r)
            r["score"], r["level"], r["reasons"] = score, level, reasons
        rows.sort(key=lambda x: (-(x.get("score", 0)), not x.get("beacon", False)))
        return rows
    except Exception:
        return []


@app.get("/api/connections")
def api_connections(source: str = Query("auto"), established_only: bool = Query(False)):
    source = (source or "auto").lower()
    rows: List[Dict] = []
    if source in ("auto", "psutil"):
        rows = _collect_connections_psutil(established_only=established_only)
    if source in ("auto", "lsof") and not rows:
        rows = _collect_connections_lsof(established_only=established_only)
    return JSONResponse({
        "ts": _now(),
        "rows": rows,
        "source": source,
    })


@app.get("/api/action_plan")
def api_action_plan(pid: int = Query(...), raddr: str = Query("")):
    """Devuelve un plan de acción sugerido para investigar/contener."""
    # Resolver ruta del ejecutable para comandos que lo requieren en macOS
    exe_path = ""
    try:
        p = psutil.Process(pid)
        exe_path = p.exe() or ""
    except Exception:
        exe_path = ""

    plan: List[str] = []
    plan.append(f"Identificar proceso {pid}: ps -fp {pid} && lsof -p {pid}")
    if raddr:
        plan.append(f"Inspeccionar conexión remota {raddr}: whois/ipinfo y reputación")
    plan.append("Capturar tráfico focalizado 60s: sudo tcpdump -i any host " + (raddr.split(":")[0] if raddr else "<IP>"))
    if exe_path:
        plan.append("Revisar binario: strings '" + exe_path + "' | less")
        plan.append("Hash y verificación: shasum -a 256 '" + exe_path + "'")
        plan.append("Firma y Gatekeeper: codesign -dv --verbose=4 '" + exe_path + "' && spctl -a -vv '" + exe_path + "'")
    else:
        plan.append("No se pudo resolver la ruta del ejecutable (permisos o proceso efímero)")
    plan.append("Listar archivos abiertos: lsof -p " + str(pid))
    plan.append("Contención temporal: sudo kill -STOP " + str(pid) + " (y evaluar)")
    plan.append("Reglas de firewall: ufw/pf para bloquear IP/puerto si es malicioso")
    plan.append("Persistencia: chequear servicios/cron/launchd del usuario del proceso")
    plan.append("Post-mortem: kill -TERM, volcado (gcore) y análisis fuera de línea")

    return JSONResponse({"plan": plan})


@app.get("/api/export_case")
def api_export_case(pid: int = Query(...), raddr: str = Query(""), fmt: str = Query("json")):
    """Exporta evidencia de un caso (PID + destino) en JSON o Markdown.
    - Incluye: PID, proceso, usuario, ejecutable, firma/notarización/quarantine,
      destino, puerto/servicio, score, nivel, razones, timestamps y stats.
    """
    fmt = (fmt or "json").lower()
    now_ts = _now()

    # Resolver proceso
    proc_name = "?"
    user = "?"
    exe = ""
    try:
        p = psutil.Process(pid)
        proc_name = p.name() or "?"
        user = p.username() or "?"
        exe = p.exe() or ""
    except Exception:
        pass

    sign = _sign_info_for_exe(exe) if exe else {"signed": False, "apple": False, "notarized": False, "quarantine": False, "authorities": []}
    exe_mtime = None
    exe_recent = False
    try:
        if exe and os.path.isfile(exe):
            exe_mtime = float(os.path.getmtime(exe))
            exe_recent = (now_ts - exe_mtime) <= (72*3600)
    except Exception:
        exe_mtime = None

    # Normaliza raddr (acepta "ip" o "ip:puerto")
    dst_key = raddr or ""
    if dst_key and ":" not in dst_key:
        # Buscar la entrada más reciente para ese host en HIST
        candidates = [(k, (HIST[(pid, k)][-1] if HIST[(pid, k)] else 0)) for (pp, k) in list(HIST.keys()) if pp == pid and k.split(":")[0] == dst_key]
        if candidates:
            candidates.sort(key=lambda x: -x[1])
            dst_key = candidates[0][0]

    # Derivar puerto y servicio
    dport = None
    if dst_key and ":" in dst_key:
        try:
            dport = int(dst_key.rsplit(":", 1)[1])
        except Exception:
            dport = None
    service = _service_name(dport)

    # Status si está activo
    status = ""
    try:
        for c in psutil.net_connections(kind="inet"):
            if (getattr(c, "pid", None) or -1) != pid:
                continue
            if _fmt_addr(getattr(c, "raddr", None)) == dst_key:
                status = str(getattr(c, "status", ""))
                break
    except Exception:
        status = ""

    # Unique dsts por PID a partir de HIST
    unique_hosts = set()
    try:
        for (pp, k) in HIST.keys():
            if pp == pid and k:
                unique_hosts.add(k.split(":")[0])
    except Exception:
        pass

    # Beacon + razones/score
    beacon = bool(dst_key and _beacon_flag(pid, dst_key, now_ts))
    row_for_score = {
        "pid": pid,
        "exe": exe,
        "raddr": dst_key,
        "dport": dport,
        "beacon": beacon,
        "unique_dsts": len(unique_hosts),
        "signed": bool(sign.get("signed")),
        "apple": bool(sign.get("apple")),
        "quarantine": bool(sign.get("quarantine")),
    }
    score, level, reasons = _score_row(row_for_score)

    # Timestamps del histórico
    ts_list = list(HIST[(pid, dst_key)]) if dst_key else []
    ts_list_sorted = sorted(ts_list)
    recent_60s = [t for t in ts_list_sorted if now_ts - t <= 60]
    intervals = [b - a for a, b in zip(ts_list_sorted[:-1], ts_list_sorted[1:])]
    try:
        interval_stddev = float(np.std(intervals)) if intervals else 0.0
    except Exception:
        interval_stddev = 0.0

    evidence = {
        "generated_at": now_ts,
        "generated_at_iso": _ts_iso(now_ts),
        "pid": pid,
        "proc": proc_name,
        "user": user,
        "exe": exe,
        "signature": {
            "signed": bool(sign.get("signed")),
            "apple": bool(sign.get("apple")),
            "notarized": bool(sign.get("notarized")),
            "quarantine": bool(sign.get("quarantine")),
            "authorities": sign.get("authorities", []),
        },
        "exe_mtime": exe_mtime,
        "exe_mtime_iso": _ts_iso(exe_mtime) if exe_mtime else None,
        "exe_recent": bool(exe_recent),
        "destination": dst_key,
        "dport": dport,
        "service": service,
        "status": status,
        "unique_dsts": len(unique_hosts),
        "score": score,
        "level": level,
        "reasons": reasons,
        "beacon": beacon,
        "timestamps": ts_list_sorted,
        "timestamps_iso": [_ts_iso(t) for t in ts_list_sorted],
        "stats": {
            "count": len(ts_list_sorted),
            "count_last_60s": len(recent_60s),
            "first_seen": ts_list_sorted[0] if ts_list_sorted else None,
            "first_seen_iso": _ts_iso(ts_list_sorted[0]) if ts_list_sorted else None,
            "last_seen": ts_list_sorted[-1] if ts_list_sorted else None,
            "last_seen_iso": _ts_iso(ts_list_sorted[-1]) if ts_list_sorted else None,
            "intervals": intervals,
            "interval_stddev": interval_stddev,
        },
    }

    # Construir respuesta y nombre de archivo sugerido
    safe_dst = (dst_key or "dst").replace(":", "-")
    fname = f"portwatch_case_pid{pid}_{safe_dst}"
    headers = {"Content-Disposition": f"attachment; filename={fname}.{('md' if fmt=='md' else 'json')}"}

    if fmt == "md" or fmt == "markdown":
        lines = []
        lines.append(f"# PortWatch – Caso PID {pid}")
        lines.append("")
        lines.append(f"Generado: {evidence['generated_at_iso']}")
        lines.append("")
        lines.append("## Proceso")
        lines.append(f"- PID: {pid}")
        lines.append(f"- Proceso: {proc_name}")
        lines.append(f"- Usuario: {user}")
        lines.append(f"- Ejecutable: {exe or '-'}")
        sig_txt = ("Apple" if evidence["signature"]["apple"] else ("Tercero" if evidence["signature"]["signed"] else "Sin firma"))
        if evidence["signature"]["quarantine"]:
            sig_txt += " +Quarantine"
        if evidence["signature"]["notarized"]:
            sig_txt += " +Notarized"
        lines.append(f"- Firma: {sig_txt}")
        auths = evidence["signature"].get("authorities") or []
        if auths:
            lines.append(f"- Autoridades: {', '.join(auths)}")
        lines.append("")
        lines.append("## Conexión")
        lines.append(f"- Destino: {dst_key or '-'}")
        lines.append(f"- Puerto/Servicio: {dport or '-'} / {service or ''}")
        lines.append(f"- Estado: {status or '-'}")
        lines.append(f"- Destinos únicos del PID: {len(unique_hosts)}")
        lines.append("")
        lines.append("## Riesgo")
        lines.append(f"- Nivel: {level} (score {score:.2f})")
        if reasons:
            lines.append("- Motivos:")
            for r in reasons:
                lines.append(f"  - {r}")
        lines.append(f"- Beaconing: {'sí' if beacon else 'no'} (stddev {interval_stddev:.3f}s)")
        lines.append("")
        lines.append("## Timestamps")
        if ts_list_sorted:
            lines.append("```")
            for t in evidence["timestamps_iso"]:
                lines.append(t)
            lines.append("```")
        else:
            lines.append("(no hay histórico para este destino)")
        lines.append("")
        lines.append("## Evidencia JSON")
        lines.append("````json")
        import json as _json  # local import para serializar
        lines.append(_json.dumps(evidence, ensure_ascii=False, indent=2))
        lines.append("````")
        md = "\n".join(lines)
        return Response(content=md, media_type="text/markdown; charset=utf-8", headers=headers)

    # JSON por defecto
    return JSONResponse(content=evidence, headers=headers)


@app.post("/api/proc_stop")
def api_proc_stop(pid: int = Query(...)):
    """Envía SIGSTOP a un proceso (pausa su ejecución). Requiere permisos.
    """
    try:
        if PROTECT_SELF and _is_self_or_ancestor(pid):
            return JSONResponse({"ok": False, "pid": pid, "action": "stop", "error": "Protegido: proceso del propio servidor"}, status_code=403)
        os.kill(pid, signal.SIGSTOP)
        return JSONResponse({"ok": True, "pid": pid, "action": "stop"})
    except PermissionError as e:
        return JSONResponse({"ok": False, "pid": pid, "action": "stop", "error": f"Permiso denegado: {e}"}, status_code=403)
    except ProcessLookupError:
        return JSONResponse({"ok": False, "pid": pid, "action": "stop", "error": "Proceso no encontrado"}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "pid": pid, "action": "stop", "error": str(e)}, status_code=500)


@app.post("/api/proc_kill")
def api_proc_kill(pid: int = Query(...)):
    """Envía SIGKILL a un proceso (terminación forzada). Requiere permisos.
    """
    try:
        if PROTECT_SELF and _is_self_or_ancestor(pid):
            return JSONResponse({"ok": False, "pid": pid, "action": "kill", "error": "Protegido: proceso del propio servidor"}, status_code=403)
        os.kill(pid, signal.SIGKILL)
        return JSONResponse({"ok": True, "pid": pid, "action": "kill"})
    except PermissionError as e:
        return JSONResponse({"ok": False, "pid": pid, "action": "kill", "error": f"Permiso denegado: {e}"}, status_code=403)
    except ProcessLookupError:
        return JSONResponse({"ok": False, "pid": pid, "action": "kill", "error": "Proceso no encontrado"}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "pid": pid, "action": "kill", "error": str(e)}, status_code=500)


@app.get("/health")
def health():
    return {"ok": True, "ts": _now()}


def _proc_tree_info(pid: int) -> Dict:
    """Construye info de árbol de procesos y posible label de launchctl.
    No mata nada; solo devuelve datos para decidir contención.
    """
    out: Dict[str, object] = {"pid": pid, "parents": [], "pgid": None, "children_count": 0}
    try:
        p = psutil.Process(pid)
    except Exception:
        out["error"] = "Proceso no encontrado"
        return out
    try:
        out["pgid"] = os.getpgid(pid)
    except Exception:
        out["pgid"] = None

    # Cadena de ancestros (pid, name)
    parents = []
    try:
        for pp in [p] + p.parents():
            try:
                parents.append({
                    "pid": pp.pid,
                    "name": pp.name(),
                    "username": pp.username() if hasattr(pp, 'username') else "",
                })
            except Exception:
                parents.append({"pid": pp.pid, "name": "?", "username": ""})
    except Exception:
        pass
    out["parents"] = parents

    # Conteo de descendientes
    try:
        out["children_count"] = len(p.children(recursive=True))
    except Exception:
        out["children_count"] = 0

    # launchctl label (solo macOS)
    label = None
    domain = None
    plist_path = None
    if _is_macos():
        try:
            proc = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    m = re.match(r"^\s*(\d+)\s+[-\d]+\s+(\S+)$", line.strip())
                    if m and int(m.group(1)) == pid:
                        label = m.group(2)
                        break
        except Exception:
            pass
        # Deducir dominio gui/<uid> por defecto
        if label:
            try:
                uid = None
                try:
                    uid = psutil.Process(pid).uids().real  # type: ignore[attr-defined]
                except Exception:
                    uid = os.getuid()
                domain = f"gui/{uid}"
            except Exception:
                domain = None
            # Intentar obtener la ruta del plist
            try:
                if domain:
                    pr = subprocess.run(["launchctl", "print", f"{domain}/{label}"], capture_output=True, text=True)
                    text = (pr.stdout or "") + (pr.stderr or "")
                    # Buscar claves comunes
                    for ln in text.splitlines():
                        if "path =" in ln:
                            plist_path = ln.split("path =", 1)[1].strip()
                            break
                        if "Program =" in ln and not plist_path:
                            plist_path = ln.split("Program =", 1)[1].strip()
            except Exception:
                pass
    out["launchd"] = {"label": label, "domain": domain, "path": plist_path}
    return out


@app.get("/api/proc_tree")
def api_proc_tree(pid: int = Query(...)):
    return JSONResponse(_proc_tree_info(pid))


@app.post("/api/proc_kill_tree")
def api_proc_kill_tree(pid: int = Query(...)):
    """Mata recursivamente el proceso y todos sus hijos (SIGKILL),
    evitando matar al propio servidor si está protegido.
    """
    try:
        if PROTECT_SELF and _is_self_or_ancestor(pid):
            return JSONResponse({"ok": False, "pid": pid, "error": "Protegido: proceso del propio servidor"}, status_code=403)

        target = psutil.Process(pid)
        # Primero matar hijos recursivamente
        children = target.children(recursive=True)
        killed: List[int] = []
        for ch in sorted(children, key=lambda c: len(c.parents()), reverse=True):
            try:
                if PROTECT_SELF and _is_self_or_ancestor(ch.pid):
                    continue
                os.kill(ch.pid, signal.SIGKILL)
                killed.append(ch.pid)
            except Exception:
                pass
        # Luego el proceso objetivo
        try:
            os.kill(pid, signal.SIGKILL)
            killed.append(pid)
        except Exception:
            pass
        return JSONResponse({"ok": True, "pid": pid, "killed": killed})
    except ProcessLookupError:
        return JSONResponse({"ok": False, "pid": pid, "error": "Proceso no encontrado"}, status_code=404)
    except PermissionError as e:
        return JSONResponse({"ok": False, "pid": pid, "error": f"Permiso denegado: {e}"}, status_code=403)
    except Exception as e:
        return JSONResponse({"ok": False, "pid": pid, "error": str(e)}, status_code=500)


@app.post("/api/proc_bootout")
def api_proc_bootout(pid: int = Query(...)):
    """Intenta descargar/deshabilitar el servicio launchctl asociado al PID (macOS).
    Sin sudo: funciona para LaunchAgents de usuario. Devuelve salida de comandos.
    """
    if not _is_macos():
        return JSONResponse({"ok": False, "error": "Solo disponible en macOS"}, status_code=400)
    info = _proc_tree_info(pid)
    label = (info.get("launchd") or {}).get("label")
    domain = (info.get("launchd") or {}).get("domain")
    if not label or not domain:
        return JSONResponse({"ok": False, "error": "No se detectó label/domain de launchctl para el PID"}, status_code=404)
    cmds = [
        ["launchctl", "bootout", f"{domain}", label],
        ["launchctl", "disable", f"{domain}/{label}"],
        ["launchctl", "remove", label],
    ]
    results = []
    for cmd in cmds:
        try:
            pr = subprocess.run(cmd, capture_output=True, text=True)
            results.append({
                "cmd": " ".join(cmd),
                "rc": pr.returncode,
                "stdout": pr.stdout,
                "stderr": pr.stderr,
            })
        except Exception as e:
            results.append({"cmd": " ".join(cmd), "error": str(e)})
    return JSONResponse({"ok": True, "label": label, "domain": domain, "results": results})


@app.post("/api/proc_kill_pgid")
def api_proc_kill_pgid(pid: int = Query(...)):
    """Mata a todos los procesos en el mismo process group del PID dado (SIGKILL).
    Útil para scripts que relanzan hijos desde el mismo grupo.
    """
    try:
        pgid = os.getpgid(pid)
    except Exception as e:
        return JSONResponse({"ok": False, "pid": pid, "error": f"No se pudo obtener PGID: {e}"}, status_code=400)
    try:
        # Proteger al propio servidor por grupo
        try:
            my_pgid = os.getpgid(OWN_PID)
        except Exception:
            my_pgid = None
        if PROTECT_SELF and my_pgid is not None and pgid == my_pgid:
            return JSONResponse({"ok": False, "pid": pid, "error": "Protegido: grupo del propio servidor"}, status_code=403)
        os.killpg(pgid, signal.SIGKILL)
        return JSONResponse({"ok": True, "pid": pid, "pgid": pgid, "action": "kill_pgid"})
    except PermissionError as e:
        return JSONResponse({"ok": False, "pid": pid, "pgid": pgid, "error": f"Permiso denegado: {e}"}, status_code=403)
    except ProcessLookupError:
        return JSONResponse({"ok": False, "pid": pid, "pgid": pgid, "error": "Grupo no encontrado"}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "pid": pid, "pgid": pgid, "error": str(e)}, status_code=500)

if __name__ == "__main__":
    # Ejecución directa: uvicorn server:app --reload
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

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
import logging
import secrets
from collections import defaultdict, deque
from typing import Dict, List, Tuple
from pathlib import Path

import psutil
import numpy as np
from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import Response
from datetime import datetime
import signal
import signal
import asyncio
import httpx
import json
import geoip2.database
import gzip
import shutil
from backend.utils.dns_sniffer import sniffer  # Import the sniffer instance
from backend.utils import dns_analyzer

ABUSEIPDB_KEY = os.getenv("ABUSEIPDB_KEY", "")
CONFIG_FILE = Path.home() / ".portwatch.json"
GEOIP_DB_PATH = Path.home() / ".portwatch_geoip.mmdb"
# URL directa a DB-IP Lite (Country) en formato MMDB
# Nota: Usamos una URL estable o instruimos al usuario. 
# Para demo, usaremos una URL de descarga directa si es posible, o simularemos.
# DB-IP Lite es CC-BY 4.0.
GEOIP_DOWNLOAD_URL = "https://download.db-ip.com/free/dbip-country-lite-2024-11.mmdb.gz" 
# Fallback a una URL genérica si la fecha cambia, o lógica dinámica.
# Por simplicidad usaremos una URL fija de ejemplo o instruiremos.
# Mejor opción: Usar un mirror confiable o la URL oficial que requiere parsing.
# Para este MVP, usaremos una URL que sabemos funciona o un placeholder.
# Vamos a usar una URL de mmdb-server que suele tener updates.
GEOIP_URL = "https://download.db-ip.com/free/dbip-country-lite-2025-11.mmdb.gz"

IP_REP_CACHE: Dict[str, Tuple[float, int]] = {}  # ip -> (ts, score)
IP_REP_TTL = 3600.0  # 1 hora


SENSITIVE_PORTS = {22, 23, 25, 445, 3389, 5900}
# Hints por puertos característicos
MINING_PORTS = {3333, 4444}
TOR_PORTS = set(range(9001, 9031))  # 9001–9030
TMP_HINTS = ("/tmp", "/private/tmp", "/var/tmp", "/dev/shm")


# Historial de timestamps por (pid, dst)
HIST = defaultdict(lambda: deque(maxlen=200))
WINDOW_SECONDS = 120
SIGN_CACHE: Dict[str, Tuple[float, Dict]] = {}
SIGN_CACHE_TTL = 300.0  # segundos
OWN_PID = os.getpid()
PROTECT_SELF = os.getenv("PW_PROTECT_SELF", "1") != "0"
ACTION_TOKEN = os.getenv("PW_ACTION_TOKEN") or secrets.token_hex(16)

# Global state shared with tray_app (if running in same process)
CONNECTIONS: Dict[str, Dict] = {}
PARANOID_MODE = False
KILLED_PROCESSES: List[Dict] = []  # Track all auto-killed processes
MAX_KILLED_HISTORY = 50  # Keep last 50 kills

# Network Speed Tracking
LAST_NET_IO = None
LAST_NET_TIME = 0
CURRENT_NET_SPEED = {"up": 0, "down": 0}  # bytes/sec

# Disk I/O Tracking for Ransomware Detection
# pid -> (timestamp, write_bytes)
PROC_IO_CACHE: Dict[int, Tuple[float, int]] = {}


# Icon Cache
from functools import lru_cache
import plistlib
import tempfile
import subprocess
from fastapi.responses import Response

@lru_cache(maxsize=100)
def get_app_icon_png(exe_path: str) -> bytes:
    """Extract icon from .app bundle and convert to PNG"""
    if not exe_path or ".app/" not in exe_path:
        return None
        
    try:
        app_path = exe_path.split(".app/")[0] + ".app"
        contents_path = os.path.join(app_path, "Contents")
        plist_path = os.path.join(contents_path, "Info.plist")
        
        if not os.path.exists(plist_path):
            return None

        with open(plist_path, 'rb') as f:
            plist = plistlib.load(f)
        
        icon_name = plist.get('CFBundleIconFile')
        if not icon_name:
            return None
            
        if not icon_name.endswith('.icns'):
            icon_name += '.icns'
            
        icon_path = os.path.join(contents_path, "Resources", icon_name)
        
        if not os.path.exists(icon_path):
            return None
            
        # Convert to PNG using sips
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name
            
        cmd = [
            "sips", 
            "-s", "format", "png", 
            "--resampleHeightWidth", "64", "64", 
            icon_path, 
            "--out", tmp_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        with open(tmp_path, "rb") as f:
            png_data = f.read()
            
        os.unlink(tmp_path)
        return png_data
    except Exception as e:
        LOG.warning(f"Failed to extract icon for {exe_path}: {e}")
        return None



LOG = logging.getLogger("portwatch.server")
if not LOG.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Alert Engine imports (after LOG is defined)
try:
    from backend.core.alert_engine import AlertEngine
    from backend.utils.notifier import get_notifier
    
    # Initialize global instances
    alert_engine = AlertEngine()
    notifier = get_notifier()
    ALERT_MODE_ENABLED = True
    LOG.info("Alert mode enabled")
    print("✅ Alert mode ENABLED successfully")
except Exception as e:
    ALERT_MODE_ENABLED = False
    alert_engine = None
    notifier = None
    LOG.warning(f"Alert mode disabled: {e}")
    print(f"❌ Alert mode DISABLED: {e}")
    import traceback
    traceback.print_exc()


# Start DNS Sniffer
try:
    sniffer.start()
except Exception as e:
    print(f"Failed to start DNS Sniffer: {e}")

app = FastAPI(title="PortWatch Web Panel")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    """Add no-cache headers to prevent aggressive browser caching"""
    response = await call_next(request)
    
    # Add no-cache headers for HTML, JS, CSS and root path
    path = request.url.path
    if path == "/" or path.endswith(('.html', '.js', '.css')):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response

# 1x1 transparent PNG
TRANSPARENT_PIXEL = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

@app.get("/api/icon/{pid}")
async def get_process_icon(pid: int):
    """Get the icon for a process ID"""
    try:
        proc = psutil.Process(pid)
        exe = proc.exe()
        icon_data = get_app_icon_png(exe)
        
        if icon_data:
            return Response(content=icon_data, media_type="image/png", headers={"X-Icon-Found": "true"})
            
        # Return transparent pixel instead of 404 to avoid console errors
        return Response(content=TRANSPARENT_PIXEL, media_type="image/png", headers={"X-Icon-Found": "false"})
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return Response(content=TRANSPARENT_PIXEL, media_type="image/png", headers={"X-Icon-Found": "false"})
    except Exception as e:
        LOG.error(f"Error fetching icon for PID {pid}: {e}")
        # Even on error, return transparent to keep console clean
        return Response(content=TRANSPARENT_PIXEL, media_type="image/png", headers={"X-Icon-Found": "false"})


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()


def _base_path() -> Path:
    """Devuelve la carpeta base del proyecto (compatible con PyInstaller)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _index_html_path() -> Path:
    """Ruta del index.html ya sea en dev o empaquetado."""
    candidate = _base_path() / "index.html"
    return candidate


def _frontend_dist_path() -> Path:
    """Ruta de los archivos estáticos del frontend (React build)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # En modo empaquetado, esperamos que la carpeta 'frontend' esté en la raíz temporal
        return Path(sys._MEIPASS) / "frontend"
    # En desarrollo, buscamos frontend/dist relativo a server.py
    return Path(__file__).resolve().parent / "frontend" / "dist"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Mantener conexión viva, esperar comandos si fuera necesario
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)



def _load_config() -> Dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
    except Exception as e:
        LOG.error(f"Error loading config: {e}")
    return {}

def _save_config(cfg: Dict):
    try:
        # Merge with existing
        current = _load_config()
        current.update(cfg)
        # Write with 600 permissions
        if not CONFIG_FILE.exists():
            CONFIG_FILE.touch(mode=0o600)
        CONFIG_FILE.write_text(json.dumps(current, indent=2))
    except Exception as e:
        LOG.error(f"Error saving config: {e}")

@app.get("/api/config")
async def get_config():
    cfg = _load_config()
    # Mask keys for security
    if cfg.get("abuseipdb_key"):
        cfg["abuseipdb_key"] = "********" + cfg["abuseipdb_key"][-4:]
    return cfg

@app.post("/api/config")
async def update_config(request: Request):
    data = await request.json()
    # Only save allowed keys
    to_save = {}
    if "abuseipdb_key" in data:
        to_save["abuseipdb_key"] = data["abuseipdb_key"]
    
    if to_save:
        _save_config(to_save)
        # Update global var immediately
        global ABUSEIPDB_KEY
        ABUSEIPDB_KEY = to_save.get("abuseipdb_key", ABUSEIPDB_KEY)
        
    return {"ok": True}


class GeoIPManager:
    def __init__(self):
        self.reader = None
        self.load()

    def load(self):
        try:
            if GEOIP_DB_PATH.exists():
                self.reader = geoip2.database.Reader(str(GEOIP_DB_PATH))
                LOG.info("GeoIP DB loaded")
        except Exception as e:
            LOG.error(f"Error loading GeoIP DB: {e}")

    def lookup(self, ip: str) -> Dict:
        if not self.reader:
            return {}
        try:
            # DB-IP Lite Country no tiene city/coords precisas, pero podemos intentar
            # Si el usuario baja la City version (más pesada), mejor.
            # Intentaremos leer country.
            resp = self.reader.country(ip)
            return {
                "iso": resp.country.iso_code,
                "name": resp.country.name
            }
        except Exception:
            return {}

geoip_manager = GeoIPManager()

@app.get("/api/geoip/status")
async def geoip_status():
    exists = GEOIP_DB_PATH.exists()
    size_mb = round(GEOIP_DB_PATH.stat().st_size / (1024*1024), 2) if exists else 0
    return {"exists": exists, "size_mb": size_mb}

@app.post("/api/geoip/download")
async def geoip_download():
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", GEOIP_URL, follow_redirects=True) as resp:
                if resp.status_code != 200:
                    return JSONResponse({"error": f"Status {resp.status_code}"}, status_code=500)
                
                # Descargar a temporal
                tmp_gz = GEOIP_DB_PATH.with_suffix(".mmdb.gz")
                with open(tmp_gz, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
                
                # Descomprimir
                with gzip.open(tmp_gz, "rb") as f_in:
                    with open(GEOIP_DB_PATH, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                tmp_gz.unlink()
                geoip_manager.load()
                return {"ok": True}
    except Exception as e:
        LOG.error(f"GeoIP download error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/factory_reset")
async def factory_reset(request: Request):
    """
    Factory Reset: Wipes all data and resets application state.
    - Deletes config file
    - Deletes GeoIP DB
    - Deletes Rules DB
    - Clears in-memory caches
    """
    # Verify auth (optional but recommended, though this is a local app)
    # if not _auth_ok(request):
    #     return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        LOG.warning("⚠️ INITIATING FACTORY RESET ⚠️")
        
        # 1. Delete Config File
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            LOG.info(f"Deleted config: {CONFIG_FILE}")
            
        # 2. Delete GeoIP DB
        if GEOIP_DB_PATH.exists():
            GEOIP_DB_PATH.unlink()
            LOG.info(f"Deleted GeoIP DB: {GEOIP_DB_PATH}")
            
        # 3. Delete Rules DB
        # We need to close the connection in RulesManager if it stays open, 
        # but currently it opens/closes per request.
        # However, we should probably delete the whole .portwatch folder or just the db
        rules_db_path = Path.home() / ".portwatch" / "rules.db"
        if rules_db_path.exists():
            try:
                rules_db_path.unlink()
                LOG.info(f"Deleted Rules DB: {rules_db_path}")
            except Exception as e:
                LOG.error(f"Failed to delete rules DB: {e}")

        # 4. Clear In-Memory Caches
        global IP_REP_CACHE, SIGN_CACHE, HIST, CONNECTIONS, KILLED_PROCESSES, ABUSEIPDB_KEY
        IP_REP_CACHE.clear()
        SIGN_CACHE.clear()
        HIST.clear()
        CONNECTIONS.clear()
        KILLED_PROCESSES.clear()
        ABUSEIPDB_KEY = ""
        
        # 5. Reset Alert Engine State
        if alert_engine:
            alert_engine.seen_connections.clear()
            alert_engine.pending_alerts.clear()
            alert_engine.last_notifications.clear()
            # Reset settings to default
            alert_engine.settings = {
                "enabled": False,
                "alert_level": "high",
                "auto_allow_signed": False,
                "notification_cooldown": 60
            }
            
        # 6. Reset GeoIP Manager
        geoip_manager.reader = None
        
        LOG.info("✅ Factory Reset Complete")
        return {"ok": True}
        
    except Exception as e:
        LOG.error(f"Factory reset failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

def _scan_resource_threats() -> List[Dict]:
    """
    Scan all processes for resource-based threats (high CPU/RAM).
    Returns list of threat processes that should be killed in Paranoid Mode.
    """
    threats = []
    now_ts = _now()
    
    # Cleanup IO cache for dead processes
    current_pids = set(psutil.pids())
    for pid in list(PROC_IO_CACHE.keys()):
        if pid not in current_pids:
            del PROC_IO_CACHE[pid]

    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cpu_percent', 'memory_info', 'username']):
            try:
                pid = proc.info['pid']
                if pid <= 0:
                    continue
                
                # Skip self and system processes
                if PROTECT_SELF and _is_self_or_ancestor(pid):
                    continue
                
                # Get resource usage
                cpu = proc.info.get('cpu_percent')
                if cpu is None:
                    cpu = 0.0
                mem_info = proc.info.get('memory_info')
                mem_bytes = mem_info.rss if mem_info else 0
                mem_mb = mem_bytes / (1024 * 1024)
                
                mem_mb = mem_bytes / (1024 * 1024)
                
                # Calculate Disk Write Speed
                try:
                    io = proc.io_counters()
                    write_bytes = io.write_bytes if io else 0
                except Exception:
                    write_bytes = 0
                    
                write_speed_mb = 0.0
                
                if pid in PROC_IO_CACHE:
                    last_ts, last_bytes = PROC_IO_CACHE[pid]
                    delta_t = now_ts - last_ts
                    if delta_t > 0:
                        delta_bytes = write_bytes - last_bytes
                        # Handle counter wrap or restart (though unlikely for same pid)
                        if delta_bytes >= 0:
                            write_speed_mb = (delta_bytes / delta_t) / (1024 * 1024)
                        
                        # Debug raw values
                        if pid == 48028 or write_speed_mb > 0: # Hard to know PID, so just log if delta > 0
                             pass
                
                # Update cache
                PROC_IO_CACHE[pid] = (now_ts, write_bytes)
                
                exe = proc.info.get('exe') or ""

                exe = proc.info.get('exe') or ""
                name = proc.info.get('name', '?')
                user = proc.info.get('username', '?')
                
                # Get signature info
                sign_info = _sign_info_for_exe(exe) if exe else {"signed": False, "apple": False}
                is_unsigned = not sign_info.get("signed") and not sign_info.get("apple")
                is_tmp = any(hint in exe for hint in TMP_HINTS) if exe else False
                
                # Threat scoring
                threat_score = 0
                reasons = []
                
                # High CPU (>70%)
                if cpu > 70:
                    threat_score += 3
                    reasons.append(f"CPU: {cpu:.1f}%")
                elif cpu > 50:
                    threat_score += 1
                    reasons.append(f"CPU: {cpu:.1f}%")
                
                # High RAM (>1GB)
                if mem_mb > 1024:
                    threat_score += 2
                    reasons.append(f"RAM: {mem_mb:.0f}MB")
                elif mem_mb > 512:
                    threat_score += 1
                    reasons.append(f"RAM: {mem_mb:.0f}MB")
                
                # Unsigned executable
                if is_unsigned:
                    threat_score += 2
                    reasons.append("Sin firma")
                
                # Running from /tmp (major red flag)
                if is_tmp:
                    threat_score += 3
                    reasons.append("Ejecutando desde /tmp")

                # Ransomware Heuristic: High Write Speed + CPU
                # Thresholds: > 50 MB/s Write AND > 40% CPU
                if write_speed_mb > 50 and cpu > 40:
                    threat_score += 5
                    reasons.append(f"RANSOMWARE: Write {write_speed_mb:.1f}MB/s + CPU {cpu:.1f}%")
                elif write_speed_mb > 20 and cpu > 30:
                     # Suspicious but maybe just copying files
                    threat_score += 2
                    reasons.append(f"High I/O: {write_speed_mb:.1f}MB/s")
                
                
                # If threat score >= 4, it's a threat
                # Examples:
                #  - High CPU (70%) + Unsigned = 3 + 2 = 5 ✓
                #  - High RAM (1GB) + /tmp = 2 + 3 = 5 ✓
                #  - Medium CPU (50%) + Medium RAM (512MB) + Unsigned + /tmp = 1 + 1 + 2 + 3 = 7 ✓
                if threat_score >= 4:
                    threats.append({
                        "pid": pid,
                        "proc": name,
                        "user": user,
                        "exe": exe,
                        "cpu": cpu,
                        "mem_mb": mem_mb,
                        "threat_score": threat_score,
                        "reasons": reasons,
                        "unsigned": is_unsigned,
                        "tmp": is_tmp
                    })
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
    except Exception as e:
        LOG.error(f"Error scanning resource threats: {e}")
    
    return threats


async def resource_monitor_loop():
    """Background task that monitors resource usage and kills threats in Paranoid Mode."""
    await asyncio.sleep(5)  # Wait 5s on startup to let system stabilize
    
    while True:
        if PARANOID_MODE:
            try:
                loop = asyncio.get_running_loop()
                threats = await loop.run_in_executor(None, _scan_resource_threats)
                
                for threat in threats:
                    pid = threat["pid"]
                    proc = threat["proc"]
                    threat_score = threat["threat_score"]
                    reasons = ", ".join(threat["reasons"])
                    
                    LOG.warning(f"RESOURCE THREAT DETECTED: {proc} (PID {pid}) - Score: {threat_score} - {reasons}")
                    
                    # Auto-kill in Paranoid Mode
                    success, msg = _kill_pgid(pid)
                    if success:
                        LOG.error(f"🔴 PARANOID MODE KILL: {proc} (PID {pid}) - Score: {threat_score} | {reasons}")
                        
                        # Record kill for UI display
                        kill_record = {
                            "timestamp": time.time(),
                            "pid": pid,
                            "proc": proc,
                            "reason": reasons,
                            "type": "resource",
                            "score": threat_score
                        }
                        KILLED_PROCESSES.insert(0, kill_record)
                        if len(KILLED_PROCESSES) > MAX_KILLED_HISTORY:
                            KILLED_PROCESSES.pop()
                    else:
                        LOG.error(f"❌ PARANOID MODE: Failed to kill PID {pid}: {msg}")
                        
            except Exception as e:
                LOG.error(f"Error in resource_monitor_loop: {e}")
        
        await asyncio.sleep(3.0)  # Scan every 3 seconds


async def broadcast_loop():
    """Bucle infinito que emite el estado de conexiones cada 2s."""
    while True:
        if manager.active_connections:
            try:
                # Ejecutar recolección en thread pool para no bloquear
                loop = asyncio.get_running_loop()
                
                # Lógica "auto": intentar psutil, si devuelve poco y es mac, probar lsof
                rows = await loop.run_in_executor(None, _collect_connections_psutil, False)
                
                # Fallback simple: si psutil devuelve < 2 conexiones y estamos en mac, probar lsof
                if len(rows) < 2 and sys.platform == "darwin":
                    rows_lsof = await loop.run_in_executor(None, _collect_connections_lsof, False)
                    if len(rows_lsof) > len(rows):
                        rows = rows_lsof

                # ========== INTERACTIVE ALERT MODE ==========
                # Alert processing happens below in the main loop (line ~587)
                # This duplicate code has been removed to avoid double-processing

                # Calculate Network Speed
                global LAST_NET_IO, LAST_NET_TIME, CURRENT_NET_SPEED
                try:
                    current_io = psutil.net_io_counters()
                    current_time = time.time()
                    
                    if LAST_NET_IO and LAST_NET_TIME > 0:
                        time_diff = current_time - LAST_NET_TIME
                        if time_diff > 0:
                            bytes_sent = current_io.bytes_sent - LAST_NET_IO.bytes_sent
                            bytes_recv = current_io.bytes_recv - LAST_NET_IO.bytes_recv
                            
                            CURRENT_NET_SPEED = {
                                "up": max(0, int(bytes_sent / time_diff)),
                                "down": max(0, int(bytes_recv / time_diff))
                            }
                    
                    LAST_NET_IO = current_io
                    LAST_NET_TIME = current_time
                except Exception as e:
                    LOG.error(f"Error calculating net speed: {e}")

                msg = {
                    "ts": _now(),
                    "rows": rows,
                    "source": "auto",
                    "killed_processes": KILLED_PROCESSES[:20],  # Send last 20 kills
                    "net_speed": CURRENT_NET_SPEED,
                    "pending_alerts": alert_engine.get_pending_alerts() if ALERT_MODE_ENABLED else []
                }
                
                # Update global state for tray_app
                # We use a fresh dict to avoid race conditions during iteration in other threads
                new_conns = {}
                for r in rows:
                    # Unique key for connection: pid-raddr-laddr
                    key = f"{r.get('pid')}-{r.get('raddr')}-{r.get('laddr')}"
                    new_conns[key] = r

                    # ALERT ENGINE INTEGRATION
                    if ALERT_MODE_ENABLED:
                        try:
                            # Process connection for alerts and get action
                            action = alert_engine.process_connection(r)
                            
                            # ENFORCE DENY RULES - Actually kill blocked processes
                            if action == "deny":
                                pid = r.get("pid")
                                proc_name = r.get("proc", "unknown")
                                dest = r.get("raddr", "unknown")
                                
                                if pid and pid > 0:
                                    LOG.warning(f"🚫 DENY RULE MATCHED: {proc_name} (PID {pid}) -> {dest}")
                                    success, msg = _kill_pgid(pid)
                                    
                                    if success:
                                        LOG.error(f"💀 BLOCKED & KILLED: {proc_name} (PID {pid}) due to deny rule")
                                        
                                        # Record in killed processes history
                                        kill_record = {
                                            "timestamp": time.time(),
                                            "pid": pid,
                                            "proc": proc_name,
                                            "reason": f"Deny rule: {dest}",
                                            "type": "block",
                                            "destination": dest
                                        }
                                        KILLED_PROCESSES.insert(0, kill_record)
                                        if len(KILLED_PROCESSES) > MAX_KILLED_HISTORY:
                                            KILLED_PROCESSES.pop()
                                    else:
                                        LOG.error(f"❌ Failed to kill blocked process {proc_name} (PID {pid}): {msg}")
                            
                            # Enrich connection with alert info (for history persistence)
                            alert_info = alert_engine.get_alert_info_for_connection(r)
                            if alert_info:
                                r["alert_info"] = alert_info
                                
                        except Exception as e:
                            LOG.error(f"Error processing alert for {key}: {e}")
                
                global CONNECTIONS
                CONNECTIONS = new_conns

                await manager.broadcast(msg)
            except Exception as e:
                LOG.error("Error en broadcast_loop: %s", e)
        await asyncio.sleep(2.0)


@app.on_event("startup")
async def startup_event():
    """Initialize background tasks"""
    asyncio.create_task(broadcast_loop())
    asyncio.create_task(resource_monitor_loop())


def _now():
    return time.time()


def _is_macos() -> bool:
    try:
        return sys.platform.startswith("darwin")
    except Exception:
        return False


def _normalize_path(p: str) -> str:
    try:
        return Path(p).expanduser().resolve().as_posix().lower()
    except Exception:
        try:
            return p.replace("\\", "/").lower()
        except Exception:
            return p


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


def _auth_ok(request: Request) -> bool:
    """Validación simple: cookie pwtoken o header X-PW-Token debe coincidir con token en memoria."""
    try:
        cookie_val = request.cookies.get("pwtoken")
    except Exception:
        cookie_val = None
    header_val = request.headers.get("X-PW-Token")
    return cookie_val == ACTION_TOKEN or header_val == ACTION_TOKEN


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
    exe_norm = _normalize_path(row.get("exe") or "")
    if any(h in exe_norm for h in TMP_HINTS):
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

    exe_l = exe_norm
    if exe_l.startswith("/system/") or exe_l.startswith("/usr/bin") or exe_l.startswith("/usr/libexec"):
        if apple:
            score -= 0.5
    user_home = str(Path.home().as_posix()).lower()
    if exe_l.startswith(user_home):
        if ("/downloads" in exe_l or "/library/" in exe_l or "/desktop" in exe_l):

                score += 0.5
                reasons.append("Ejecutable en carpeta de usuario")
    # Compatibilidad con ruta /users/ legacy
    elif ("/users/" in exe_l and ("/downloads" in exe_l or "/library/" in exe_l)) and _is_public_ip((row.get("raddr") or "").split(":")[0]):
        score += 0.5
        reasons.append("Ejecutable en carpeta de usuario")

    # Heurística de Recursos (CPU/RAM)
    cpu_usage = row.get("cpu", 0.0)
    mem_usage = row.get("mem", 0)
    
    # CPU > 50%
    if cpu_usage > 50.0:
        score += 2.0
        reasons.append(f"Alto consumo CPU ({cpu_usage:.1f}%)")
        
    # RAM > 500 MB (500 * 1024 * 1024)
    if mem_usage > 524288000:
        mem_mb = mem_usage / (1024 * 1024)
        score += 1.0
        reasons.append(f"Alto consumo RAM ({mem_mb:.0f} MB)")
    
    # PARENT PROCESS HEURISTIC
    # If spawned by suspicious parent (bash/curl/sh) AND connecting to public IP → likely malware
    if row.get("suspicious_parent") and _is_public_ip(rhost):
        parent_name = row.get("parent_name", "unknown")
        score += 2.5
        reasons.append(f"Spawn sospechoso: lanzado por '{parent_name}'")

    # DNS Enrichment Scoring
    dns_risk = row.get("dns_risk")
    if dns_risk and dns_risk.get("score", 0) > 0:
        score += dns_risk["score"]
        if dns_risk.get("reasons"):
            reasons.extend([f"DNS: {r}" for r in dns_risk["reasons"]])

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
    # attrs=["pid", "name", "username", "exe", "cpu_percent", "memory_info"]
    # Note: cpu_percent(interval=None) returns 0.0 on first call, but useful for subsequent calls or if psutil maintains state.
    # For better accuracy we might need a background thread, but for now we use instantaneous or cached if available.
    for p in psutil.process_iter(attrs=["pid", "name", "username", "exe", "memory_info"]):
        try:
            # cpu_percent needs to be called, it's not just an attribute in the iterator sometimes depending on psutil version
            # But process_iter with attrs usually works. Let's be safe.
            p_info = p.info
            
            # Get CPU explicitly if needed, but p.cpu_percent(interval=None) is non-blocking
            try:
                cpu = p.cpu_percent(interval=None)
            except Exception:
                cpu = 0.0
                
            mem_info = p_info.get("memory_info")
            mem_rss = mem_info.rss if mem_info else 0
            
            out[p_info["pid"]] = {
                "pid": p_info.get("pid"),
                "proc": p_info.get("name") or "?",
                "user": p_info.get("username") or "?",
                "exe": p_info.get("exe") or "",
                "cpu": cpu,
                "mem": mem_rss,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
            
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


def _run_cmd(cmd: List[str], timeout: float = 2.0) -> Tuple[int, str, str]:
    """Ejecuta comando con timeout y captura stdout/stderr."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        LOG.warning("Comando timeout: %s", " ".join(cmd))
        return 124, "", "timeout"
    except FileNotFoundError:
        LOG.warning("Comando no encontrado: %s", " ".join(cmd))
        return 127, "", "not found"
    except Exception as exc:
        LOG.warning("Error al ejecutar %s: %s", " ".join(cmd), exc)
        return 1, "", str(exc)


def _sign_info_for_exe(exe: str) -> Dict:
    if not exe:
        return {"signed": False, "apple": False, "authorities": [], "notarized": False, "quarantine": False}
    try:
        exe = os.path.realpath(exe)
    except Exception:
        exe = exe
    if not os.path.isfile(exe):
        return {"signed": False, "apple": False, "authorities": [], "notarized": False, "quarantine": False}

    # Cache
    now_ts = _now()
    cached = SIGN_CACHE.get(exe)
    if cached and (now_ts - cached[0] <= SIGN_CACHE_TTL):
        return cached[1]

    result = {"signed": False, "apple": False, "authorities": [], "notarized": False, "quarantine": False}
    # Firma
    rc, out, err = _run_cmd(["/usr/bin/codesign", "-dv", "--verbose=4", exe], timeout=2.0)
    if rc == 0 or out or err:
        parsed = _parse_codesign_output(out + err)
        result.update(parsed)

    # Gatekeeper / notarized
    rc, out, err = _run_cmd(["/usr/sbin/spctl", "-a", "-vv", exe], timeout=2.0)
    if rc != 127:  # 127 = spctl ausente
        o = (out + err).lower()
        result["notarized"] = ("accepted" in o) and ("notarized" in o or "source=apple" in o or "developer id" in o)

    # Quarantine xattr
    rc, out, err = _run_cmd(["/usr/bin/xattr", "-p", "com.apple.quarantine", exe], timeout=1.0)
    result["quarantine"] = rc == 0 and bool((out or err).strip())

    SIGN_CACHE[exe] = (now_ts, result)
    return result


def _is_public_ip(ip: str) -> bool:
    try:
        if not ip: return False
        obj = ipaddress.ip_address(ip)
        return not obj.is_private and not obj.is_loopback and not obj.is_link_local
    except ValueError:
        return False


async def _check_ip_reputation(ip: str):
    """Consulta asíncrona a AbuseIPDB con caché."""
    # Priorizar env var, luego config file
    key = ABUSEIPDB_KEY
    if not key:
        cfg = _load_config()
        key = cfg.get("abuseipdb_key", "")
    
    if not key or not _is_public_ip(ip):
        return

    now = _now()
    cached = IP_REP_CACHE.get(ip)
    if cached and (now - cached[0] < IP_REP_TTL):
        return

    # Marcamos como pendiente (ts reciente, score -1) para no spammear
    IP_REP_CACHE[ip] = (now, -1)

    try:
        async with httpx.AsyncClient() as client:
            headers = {
                'Key': key,
                'Accept': 'application/json'
            }
            params = {'ipAddress': ip, 'maxAgeInDays': 90}
            resp = await client.get('https://api.abuseipdb.com/api/v2/check', headers=headers, params=params, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                score = data.get('data', {}).get('abuseConfidenceScore', 0)
                IP_REP_CACHE[ip] = (now, score)
            else:
                LOG.warning(f"AbuseIPDB error {resp.status_code} for {ip}")
                # Backoff en caso de error
                IP_REP_CACHE[ip] = (now, -2) 
    except Exception as e:
        LOG.error(f"Error checking IP {ip}: {e}")


def _collect_connections_psutil(established_only: bool = False) -> List[Dict]:
    now_ts = _now()
    rows: List[Dict] = []

    proc_map = _proc_info_cache()

    try:
        conns = psutil.net_connections(kind="inet")
    except Exception as e:
        # En macOS sin root es normal que falle. No spammear logs.
        LOG.debug(f"psutil.net_connections fallo (esperado sin root): {e}")
        return []

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
        # Filtrar conexiones propias si está activada la protección
        if PROTECT_SELF and pid == OWN_PID:
            continue

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
        
        # PARENT PROCESS HEURISTIC
        # Detect suspicious spawning (e.g., curl | bash, sh -c malware)
        parent_name = ""
        suspicious_parent = False
        SUSPICIOUS_PARENTS = {'bash', 'sh', 'zsh', 'curl', 'wget', 'python', 'python3', 'perl', 'ruby', 'node'}
        
        try:
            if pid > 0:
                proc_obj = psutil.Process(pid)
                parent = proc_obj.parent()
                if parent:
                    parent_name = parent.name()
                    if parent_name.lower() in SUSPICIOUS_PARENTS:
                        suspicious_parent = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

        # DNS Enrichment
        domain = None
        dns_risk = None
        if c.raddr and c.raddr.ip:
            dns_info = sniffer.get_domain_for_ip(c.raddr.ip)
            if dns_info:
                domain = dns_info.get('domain')
                dns_risk = dns_info.get('analysis')
        
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
            "parent_name": parent_name,
            "suspicious_parent": suspicious_parent,
            "domain": domain,
            "dns_risk": dns_risk,
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
        r["level"] = level
        r["reasons"] = reasons
        
        # PARANOID MODE AUTO-KILL
        if PARANOID_MODE and level in ("medio", "alto"):
            pid_to_kill = r["pid"]
            # Avoid killing if pid is -1 or 0
            if pid_to_kill > 0:
                success, msg = _kill_pgid(pid_to_kill)
                if success:
                    LOG.error(f"🔴 PARANOID MODE KILL: {r['proc']} (PID {pid_to_kill}) - Risk: {level} | {', '.join(reasons)}")
                    r["status"] = "KILLED" # Mark in UI
                    
                    # Record kill for UI display
                    kill_record = {
                        "timestamp": time.time(),
                        "pid": pid_to_kill,
                        "proc": r["proc"],
                        "reason": ", ".join(reasons),
                        "type": "network",
                        "level": level,
                        "raddr": r.get("raddr", ""),
                        "dport": r.get("dport", 0)
                    }
                    KILLED_PROCESSES.insert(0, kill_record)
                    if len(KILLED_PROCESSES) > MAX_KILLED_HISTORY:
                        KILLED_PROCESSES.pop()
                else:
                    LOG.error(f"❌ PARANOID MODE: Failed to kill PID {pid_to_kill}: {msg}")
        
        # Enriquecer con reputación (si existe en caché)
        # Fix IPv6 parsing: [2001:db8::1]:443 -> 2001:db8::1
        raw_raddr = r.get("raddr", "")
        rip = ""
        if raw_raddr:
            # Si hay brackets (IPv6), extraer lo de adentro
            if raw_raddr.startswith("["):
                end_bracket = raw_raddr.find("]")
                if end_bracket != -1:
                    rip = raw_raddr[1:end_bracket]
            else:
                # IPv4 o hostname: split por el último : para quitar puerto
                if ":" in raw_raddr:
                    rip = raw_raddr.rsplit(":", 1)[0]
                else:
                    rip = raw_raddr

        if rip:
            cached_rep = IP_REP_CACHE.get(rip)
            if cached_rep and cached_rep[1] >= 0:
                r["abuse_score"] = cached_rep[1]
                if cached_rep[1] > 0:
                    r["score"] += (cached_rep[1] / 20.0) # Sumar hasta 5 puntos extra
                    # Recalcular nivel si cambió el score
                    if r["score"] >= 7.0: r["level"] = "alto"
                    elif r["score"] >= 4.0: r["level"] = "medio"

        # GeoIP
        if geoip_manager.reader:
            geo = geoip_manager.lookup(rip)
            if geo:
                r["country"] = geo.get("iso")
                r["country_name"] = geo.get("name")



    # Trigger background checks for public IPs
    # Check if we have a key (env or config)
    has_key = bool(ABUSEIPDB_KEY)
    if not has_key:
        # Check config file just in case it was updated runtime
        try:
            cfg = _load_config()
            if cfg.get("abuseipdb_key"):
                has_key = True
        except:
            pass

    if has_key:
        # Identify public IPs that need checking
        # We use a simple heuristic: if it has a country, it's likely public enough to check
        # or use _is_public_ip
        for r in rows:
            rip = r.get("raddr", "").split(":")[0]
            # Fix IPv6 parsing again just in case
            if "]:" in r.get("raddr", ""):
                 rip = r.get("raddr", "").split("]:")[0].replace("[", "")
            elif ":" in r.get("raddr", "") and not "[" in r.get("raddr", ""):
                 rip = r.get("raddr", "").split(":")[0]
            
            if rip and _is_public_ip(rip):
                # Schedule check if not in cache (checked inside function too but good to skip here)
                if rip not in IP_REP_CACHE:
                    try:
                        asyncio.create_task(_check_ip_reputation(rip))
                    except Exception as e:
                        # If loop is closed or weird state
                        pass
    # Ordenar por score desc y luego por beacon
    rows.sort(key=lambda x: (-(x.get("score", 0)), not x.get("beacon", False)))
    return rows


def _collect_connections_lsof(established_only: bool = False) -> List[Dict]:
    """Fallback para macOS usando lsof cuando psutil no tiene permisos/visibilidad."""
    rows: List[Dict] = []
    try:
        rc, out, err = _run_cmd(["lsof", "-i", "-P", "-n", "-F", "pcnTu"], timeout=3.0)
        if rc != 0:
            if rc != 127:  # 127 = no existe lsof
                LOG.warning("lsof devolvio rc=%s err=%s", rc, err.strip())
            return []
        now_ts = _now()
        current: Dict[str, object] = {"pid": -1, "proc": "?", "user": "?", "status": "", "proto": ""}
        unique_by_pid: Dict[int, set] = defaultdict(set)
        for raw in out.splitlines():
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
                # Filtrar conexiones propias si está activada la protección
                if PROTECT_SELF and pid == OWN_PID:
                    continue

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

                # DNS Enrichment (lsof doesn't provide psutil.Connection, so we parse raddr.ip)
                domain = None
                dns_risk = None
                if raddr:
                    # Extract IP from raddr (e.g., 1.2.3.4:80 -> 1.2.3.4)
                    ip_part = raddr.split(':')[0]
                    if ip_part.startswith('[') and ip_part.endswith(']'): # IPv6
                        ip_part = ip_part[1:-1]
                    
                    if _is_public_ip(ip_part): # Only query for public IPs
                        dns_info = sniffer.get_domain_for_ip(ip_part)
                        if dns_info:
                            domain = dns_info.get('domain')
                            dns_risk = dns_info.get('analysis')

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
                    "domain": domain,
                    "dns_risk": dns_risk,
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
def api_proc_stop(request: Request, pid: int = Query(...)):
    """Envía SIGTERM a un proceso (terminación agraciada). Requiere permisos.
    """
    if not _auth_ok(request):
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
    try:
        if PROTECT_SELF and _is_self_or_ancestor(pid):
            return JSONResponse({"ok": False, "pid": pid, "action": "stop", "error": "Protegido: proceso del propio servidor"}, status_code=403)
        os.kill(pid, signal.SIGTERM)
        return JSONResponse({"ok": True, "pid": pid, "action": "stop"})
    except PermissionError as e:
        return JSONResponse({"ok": False, "pid": pid, "action": "stop", "error": f"Permiso denegado: {e}"}, status_code=403)
    except ProcessLookupError:
        return JSONResponse({"ok": False, "pid": pid, "action": "stop", "error": "Proceso no encontrado"}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "pid": pid, "action": "stop", "error": str(e)}, status_code=500)


@app.post("/api/proc_kill")
def api_proc_kill(request: Request, pid: int = Query(...)):
    """Envía SIGKILL a un proceso (terminación forzada). Requiere permisos.
    """
    if not _auth_ok(request):
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
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


@app.post("/api/clear_killed_history")
def api_clear_killed_history(request: Request):
    """Limpia el historial de procesos eliminados en Modo Paranoico."""
    if not _auth_ok(request):
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
    
    global KILLED_PROCESSES
    KILLED_PROCESSES = []
    return JSONResponse({"ok": True})



@app.get("/health")
async def health():
    return {"status": "ok", "ts": time.time()}


@app.get("/api/token")
async def get_token():
    """Devuelve el token de acción para que el frontend pueda autenticarse."""
    return {"token": ACTION_TOKEN}



# ========== INTERACTIVE ALERT MODE API ==========

@app.get("/api/rules")
async def get_rules():
    """Get all active rules"""
    if not ALERT_MODE_ENABLED:
        return JSONResponse({"error": "Alert mode not enabled"}, status_code=503)
    
    try:
        from backend.core.rules_manager import rules_manager
        rules = rules_manager.get_all_rules(enabled_only=True)
        return {"ok": True, "rules": rules}
    except Exception as e:
        LOG.error(f"Error getting rules: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/rules")
async def create_rule(request: Request):
    """Create a new rule"""
    if not ALERT_MODE_ENABLED:
        return JSONResponse({"error": "Alert mode not enabled"}, status_code=503)
    
    try:
        data = await request.json()
        # Rules are created automatically by alert decisions
        # This endpoint is not used, but keeping for compatibility
        rule_id = hashlib.md5(f"{data.get('process')}{data.get('destination')}{data.get('port')}".encode()).hexdigest()
        alert_engine.rules[rule_id] = {
            "id": rule_id,
            "process": data["process"],
            "destination": data["destination"],
            "action": data["action"],
            "scope": data.get("scope", "always"),
            "port": data.get("port"),
            "protocol": data.get("protocol", "TCP"),
            "exe_path": data.get("exe_path"),
            "user_comment": data.get("user_comment"),
            "ttl_hours": data.get("ttl_hours"),
            "enabled": True,
            "created_at": datetime.utcnow().isoformat()
        }
        return {"ok": True, "rule_id": rule_id}
    except Exception as e:
        LOG.error(f"Error creating rule: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.delete("/api/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """Delete a rule by ID"""
    if not ALERT_MODE_ENABLED:
        return JSONResponse({"error": "Alert mode not enabled"}, status_code=503)
    
    try:
        from backend.core.rules_manager import rules_manager
        
        # Get rule details before deleting (to clear from cache)
        rule = rules_manager.get_rule(rule_id)
        
        # Delete the rule
        success = rules_manager.delete_rule(rule_id)
        
        if success and rule and rule['action'] == 'deny':
            # Clear this connection from seen_connections so it can alert again
            process = rule.get('process', '')
            destination = rule.get('destination', '')
            port = rule.get('port', 0)
            
            # Build connection key using same format as AlertEngine._connection_key
            conn_key = f"{process}|{destination}|{port or 0}"
            
            # Remove from seen connections
            if conn_key in alert_engine.seen_connections:
                alert_engine.seen_connections.remove(conn_key)
                LOG.info(f"Removed {conn_key} from seen connections cache after unblocking")
        
        return {"ok": success}
    except Exception as e:
        LOG.error(f"Error deleting rule: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/alerts/pending")
async def get_pending_alerts():
    """Get pending alerts awaiting user decision"""
    if not ALERT_MODE_ENABLED:
        return JSONResponse({"error": "Alert mode not enabled"}, status_code=503)
    
    try:
        alerts = alert_engine.get_pending_alerts()
        return {"ok": True, "alerts": alerts}
    except Exception as e:
        LOG.error(f"Error getting pending alerts: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/alerts/{alert_id}/decide")
async def decide_alert(alert_id: str, request: Request):
    """User decision on a pending alert"""
    if not ALERT_MODE_ENABLED:
        return JSONResponse({"error": "Alert mode not enabled"}, status_code=503)
    
    try:
        data = await request.json()
        action = data["action"]  # "allow" or "deny"
        scope = data.get("scope", "always")  # "once", "always", "temporary"
        
        success = alert_engine.decide_alert(alert_id, action, scope)
        return {"ok": success}
    except Exception as e:
        LOG.error(f"Error deciding alert: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/alerts/settings")
async def get_alert_settings():
    """Get alert settings"""
    if not ALERT_MODE_ENABLED:
        return JSONResponse({"error": "Alert mode not enabled"}, status_code=503)
    
    return {"ok": True, "settings": alert_engine.settings}


@app.post("/api/alerts/settings")
async def update_alert_settings(request: Request):
    """Update alert settings"""
    if not ALERT_MODE_ENABLED:
        return JSONResponse({"error": "Alert mode not enabled"}, status_code=503)
    
    try:
        data = await request.json()
        alert_engine.update_settings(data)
        return {"ok": True, "settings": alert_engine.settings}
    except Exception as e:
        LOG.error(f"Error updating alert settings: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/alerts/debug")
async def debug_alerts():
    """Debug endpoint to check alert engine status"""
    if not ALERT_MODE_ENABLED:
        return JSONResponse({"error": "Alert mode not available"}, status_code=503)
    
    try:
        return {
            "ok": True,
            "enabled": alert_engine.settings.get("enabled", False),
            "settings": alert_engine.settings,
            "seen_connections_count": len(alert_engine.seen_connections),
            "pending_alerts_count": len(alert_engine.get_pending_alerts()),
            "pending_alerts": alert_engine.get_pending_alerts()
        }
    except Exception as e:
        LOG.error(f"Error in debug endpoint: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/alerts/test")
async def test_alert_notification():
    """Send a test notification to verify system integration"""
    try:
        if ALERT_MODE_ENABLED:
            # Force enable alerts for the test if disabled
            was_enabled = alert_engine.settings["enabled"]
            alert_engine.settings["enabled"] = True
            
            # Create a fake connection that triggers an alert
            fake_conn = {
                "pid": 99999,
                "process": "PortWatch Test",
                "remote_addr": "127.0.0.1",
                "remote_port": 666,
                "status": "ESTABLISHED",
                "country": "TEST",
                "level": "alto", # High risk to trigger sound/focus
                "timestamp": time.time()
            }
            
            # Process it (this adds it to pending_alerts)
            # We bypass _should_alert checks by calling process_connection 
            # but we need to ensure it passes filters.
            # Actually, process_connection calls _should_alert.
            # So we need to ensure settings allow it.
            
            # Temporarily lower alert level to ensure it passes
            old_level = alert_engine.settings["alert_level"]
            alert_engine.settings["alert_level"] = "low"
            
            alert_engine.process_connection(fake_conn)
            
            # Restore settings
            alert_engine.settings["alert_level"] = old_level
            if not was_enabled:
                alert_engine.settings["enabled"] = False
                
            return {"ok": True, "message": "Test alert injected into engine"}
        else:
            return {"ok": False, "error": "Alert engine not initialized"}
            
    except Exception as e:
        LOG.error(f"Error sending test alert: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/alerts/clear_cache")
async def clear_alert_cache():
    """Clear the seen connections cache to allow re-alerting on existing connections"""
    if not ALERT_MODE_ENABLED:
        return JSONResponse({"error": "Alert mode not enabled"}, status_code=503)
    
    try:
        count = len(alert_engine.seen_connections)
        alert_engine.seen_connections.clear()
        LOG.info(f"Cleared {count} seen connections from alert cache")
        return {
            "ok": True, 
            "cleared_count": count,
            "message": f"Cleared {count} seen connections. New connections will now trigger alerts."
        }
    except Exception as e:
        LOG.error(f"Error clearing alert cache: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


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
def api_proc_kill_tree(request: Request, pid: int = Query(...)):
    """Mata recursivamente el proceso y todos sus hijos (SIGKILL),
    evitando matar al propio servidor si está protegido.
    """
    if not _auth_ok(request):
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
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
def api_proc_bootout(request: Request, pid: int = Query(...)):
    """Intenta descargar/deshabilitar el servicio launchctl asociado al PID (macOS).
    Sin sudo: funciona para LaunchAgents de usuario. Devuelve salida de comandos.
    """
    if not _auth_ok(request):
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
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


def _kill_pgid(pid: int) -> Tuple[bool, str]:
    """Helper interno para matar un grupo de procesos de forma segura."""
    try:
        pgid = os.getpgid(pid)
    except Exception as e:
        return False, f"No se pudo obtener PGID: {e}"
    
    try:
        # Proteger al propio servidor por grupo
        try:
            my_pgid = os.getpgid(OWN_PID)
        except Exception:
            my_pgid = None
            
        if PROTECT_SELF and my_pgid is not None and pgid == my_pgid:
            return False, "Protegido: grupo del propio servidor"
            
        os.killpg(pgid, signal.SIGKILL)
        return True, "Killed"
    except PermissionError as e:
        return False, f"Permiso denegado: {e}"
    except ProcessLookupError:
        return False, "Grupo no encontrado"
    except Exception as e:
        return False, str(e)


@app.post("/api/proc_kill_pgid")
def api_proc_kill_pgid(request: Request, pid: int = Query(...)):
    """Mata a todos los procesos en el mismo process group del PID dado (SIGKILL).
    Útil para scripts que relanzan hijos desde el mismo grupo.
    """
    if not _auth_ok(request):
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
    
    success, msg = _kill_pgid(pid)
    if success:
        return JSONResponse({"ok": True, "pid": pid, "action": "kill_pgid"})
    else:
        # Mapear errores comunes a status codes
        status = 500
        if "Protegido" in msg: status = 403
        elif "Permiso" in msg: status = 403
        elif "no encontrado" in msg: status = 404
        return JSONResponse({"ok": False, "pid": pid, "error": msg}, status_code=status)


@app.post("/api/set_paranoid_mode")
def api_set_paranoid_mode(request: Request, enabled: bool = Query(...)):
    """Activa o desactiva el Modo Paranoico (Auto-Kill)."""
    if not _auth_ok(request):
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
    
    global PARANOID_MODE
    PARANOID_MODE = enabled
    LOG.info(f"Paranoid Mode set to: {PARANOID_MODE}")
    return JSONResponse({"ok": True, "paranoid_mode": PARANOID_MODE})


# ============================================================================
# DNS Configuration Management Endpoints
# ============================================================================

@app.get("/api/dns-config")
def api_get_dns_config(request: Request):
    """Returns the current DNS whitelist/blacklist configuration."""
    if not _auth_ok(request):
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
    
    try:
        config = dns_analyzer.load_dns_config()
        return JSONResponse({"ok": True, "config": config})
    except Exception as e:
        LOG.error(f"Error loading DNS config: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/dns-config")
async def api_update_dns_config(request: Request):
    """Updates the DNS whitelist/blacklist configuration."""
    if not _auth_ok(request):
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
    
    try:
        data = await request.json()
        config = data.get("config", {})
        
        # Validate structure
        required_keys = ["whitelist_domains", "whitelist_suffixes", "blacklist_keywords", "blacklist_tlds"]
        if not all(k in config for k in required_keys):
            return JSONResponse({"ok": False, "error": "Invalid config structure"}, status_code=400)
        
        # Save config
        success = dns_analyzer.save_dns_config(config)
        if not success:
            return JSONResponse({"ok": False, "error": "Failed to save config"}, status_code=500)
        
        # Reload DNS analyzer lists
        dns_analyzer.reload_dns_config()
        
        LOG.info("DNS config updated successfully")
        return JSONResponse({"ok": True, "config": config})
    except Exception as e:
        LOG.error(f"Error updating DNS config: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/get_paranoid_mode")
def api_get_paranoid_mode():
    return JSONResponse({"paranoid_mode": PARANOID_MODE})

if __name__ == "__main__":
    # Ejecución directa: uvicorn server:app --reload
    import uvicorn
    # Montar estáticos al final para no ocultar API
    # Si no existe dist (ej. primera ejecución sin build), no fallar hard, pero avisar
    dist_path = _frontend_dist_path()
    if dist_path.exists():
        app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="static")
    else:
        LOG.warning("No se encontró frontend/dist en %s. Ejecuta 'npm run build' en frontend/", dist_path)

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

#!/usr/bin/env bash
# PortWatch demo – genera tráfico "sospechoso" para probar el panel
# Modos: miner | public | spray | stop

set -Eeuo pipefail

MODE="${1:-miner}"
LOOPS="${LOOPS:-12}"    # repeticiones para beaconing (>=4 en 60s dispara tu regla)
SLEEP="${SLEEP:-1}"     # segundos entre intentos
PIDFILE="/tmp/portwatch_demo.pids"
SUSP_BIN="/tmp/nc_beacon_$$"
HOSTS_DEFAULT="1.1.1.1 8.8.8.8 9.9.9.9 76.223.54.0 18.65.0.1"  # mezcla Cloud/DNS/CDN
SRV_PID=""

log(){ printf "%s\n" "$*" >&2; }
add_pid(){ echo "$1" >> "$PIDFILE"; }
have(){ command -v "$1" >/dev/null 2>&1; }

ensure_nc() {
  if ! have nc; then
    log "[x] Necesitas 'nc' (netcat) instalado."
    exit 1
  fi
}

copy_to_tmp() {
  local ncbin
  ncbin="$(command -v nc)"
  cp "$ncbin" "$SUSP_BIN"
  chmod +x "$SUSP_BIN"
  # Intento opcional de quarantine (si falla, seguimos igual)
  if have xattr; then xattr -w com.apple.quarantine "0081;PortWatchDemo;;;;" "$SUSP_BIN" || true; fi
}

start_srv_3333() {
  set +e
  ( nc -lk 127.0.0.1 3333 >/dev/null 2>&1 ) &
  SRV_PID=$!
  sleep 0.3
  if ! kill -0 "$SRV_PID" 2>/dev/null; then
    ( nc -l 3333 -k >/dev/null 2>&1 ) &
    SRV_PID=$!
    sleep 0.3
    if ! kill -0 "$SRV_PID" 2>/dev/null; then
      # Fallback Python (por si tu nc no soporta -k)
      python3 - <<'PY' &
import socket, threading, time
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
s.bind(("127.0.0.1",3333)); s.listen(5)
def run():
    while True:
        try:
            c,_=s.accept(); c.recv(512); c.close()
        except Exception:
            pass
threading.Thread(target=run,daemon=True).start()
time.sleep(3600)
PY
      SRV_PID=$!
    fi
  fi
  set -e
  add_pid "$SRV_PID"
}

beacon_loop() {
  local host="$1" port="$2" loops="${3:-$LOOPS}" sleep_s="${4:-$SLEEP}"
  (
    i=1
    while [ "$i" -le "$loops" ]; do
      "$SUSP_BIN" -w1 "$host" "$port" </dev/null >/dev/null 2>&1 || true
      sleep "$sleep_s"
      i=$((i+1))
    done
    # mantener vivo un instante para que tu colector lo vea
    sleep 5
  ) &
  add_pid "$!"
}

spray_loop() {
  local hosts="${1:-$HOSTS_DEFAULT}" loops="${2:-$LOOPS}"
  (
    i=1
    while [ "$i" -le "$loops" ]; do
      for h in $hosts; do
        "$SUSP_BIN" -w1 "$h" 443 </dev/null >/dev/null 2>&1 || true
        sleep 0.7
      done
      i=$((i+1))
    done
    sleep 5
  ) &
  add_pid "$!"
}

stop_all() {
  if [ -f "$PIDFILE" ]; then
    tac "$PIDFILE" 2>/dev/null | while read -r p; do kill "$p" 2>/dev/null || true; done
    : > "$PIDFILE"
  fi
  find /tmp -maxdepth 1 -type f -name 'nc_beacon_*' -exec rm -f {} +
  log "[*] Procesos de demo detenidos y limpiados."
}

trap 'log "[*] Saliendo";' EXIT

case "$MODE" in
  stop)
    stop_all
    exit 0
    ;;

  miner)
    ensure_nc
    copy_to_tmp
    start_srv_3333
    beacon_loop "127.0.0.1" "3333" "$LOOPS" "$SLEEP"
    ;;

  public)
    ensure_nc
    copy_to_tmp
    beacon_loop "1.1.1.1" "443" "$LOOPS" "$SLEEP"
    ;;

  spray)
    ensure_nc
    copy_to_tmp
    spray_loop "$HOSTS_DEFAULT" "$LOOPS"
    ;;

  *)
    log "Modo no reconocido: $MODE"
    log "Usa: ./portwatch_demo.sh [miner|public|spray|stop]"
    exit 2
    ;;
esac

log "[*] Modo: $MODE"
[ -n "$SRV_PID" ] && log "[*] PID servidor 3333: $SRV_PID"
log "[*] Binario temporal: $SUSP_BIN"
log "[*] PIDs en: $PIDFILE"
log "[*] Abre PortWatch: /api/connections?established_only=false y busca exe=/tmp/nc_beacon_*, beacon=true."
log "[*] Para detener todo: ./portwatch_demo.sh stop"
wait || true

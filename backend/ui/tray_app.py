#!/usr/bin/env python3
"""Pequeña app de barra de menú/bandeja para PortWatch.
 - Arranca el servidor FastAPI/uvicorn en segundo plano.
 - Abre la UI en el navegador con un clic.
 - Funciona en macOS (menubar) y Linux (tray) usando pystray.
"""
import logging
import os
import random
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw
import uvicorn
from backend.core import server
from fastapi.staticfiles import StaticFiles


HOST = os.getenv("PW_HOST", "127.0.0.1")
LOG_DIR_MAC = Path.home() / "Library" / "Logs" / "PortWatch"
LOG_DIR_LINUX = Path.home() / ".local" / "share" / "PortWatch"


def _log_path() -> Path:
    if sys.platform == "darwin":
        # Usar /tmp para asegurar que sea visible incluso si corre como root
        return Path("/tmp/portwatch.log")
    return LOG_DIR_LINUX / "tray.log"


def _setup_logging():
    log_path = _log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(log_path, encoding="utf-8")]
    if sys.stdout:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )
    logging.info("Log de PortWatch tray iniciado en %s", log_path)


def _port_in_use(host: str, port: int) -> bool:
    """True si el puerto ya está ocupado."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _choose_port() -> int:
    """Devuelve el primer puerto libre empezando en PW_PORT (default 8000)."""
    preferred = int(os.getenv("PW_PORT", "8000"))
    candidates = [preferred] + [p for p in range(preferred + 1, preferred + 6)]
    for port in candidates:
        if not _port_in_use(HOST, port):
            return port
    raise RuntimeError("No hay puertos libres en el rango configurado (PW_PORT..PW_PORT+5)")


class ServerRunner:
    """Arranca uvicorn en un hilo y permite pararlo clean."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._thread: threading.Thread | None = None
        self._server: uvicorn.Server | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def _run_server():
            # Mount frontend static files before starting server
            dist_path = _frontend_dist_path()
            if dist_path.exists():
                try:
                    # Check if already mounted (for restart scenarios)
                    # FastAPI stores routes, we check if "/" is already mounted
                    already_mounted = any(route.path == "/" for route in server.app.routes)
                    
                    if not already_mounted:
                        # Mount at root to serve the React app
                        server.app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="static")
                        logging.info("Frontend montado desde %s", dist_path)
                    else:
                        logging.info("Frontend ya estaba montado")
                except Exception as e:
                    logging.warning("No se pudo montar frontend: %s", e)
            else:
                logging.warning("No se encontró frontend/dist en %s. La UI no estará disponible.", dist_path)
            
            config = uvicorn.Config(
                server.app,
                host=self.host,
                port=self.port,
                log_level="warning",
            )
            self._server = uvicorn.Server(config)
            logging.info("Iniciando uvicorn en %s:%s", self.host, self.port)
            self._server.run()

        self._thread = threading.Thread(target=_run_server, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)


def _wait_until_up(host: str, port: int, timeout: float = 10.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if _port_in_use(host, port):
            return True
        time.sleep(0.3)
    return False


def _base_path() -> Path:
    """Base del paquete (compatible con PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def _frontend_dist_path() -> Path:
    """Ruta de los archivos estáticos del frontend (React build)."""
    base = _base_path()
    if getattr(sys, "frozen", False):
        # En modo empaquetado, esperamos que la carpeta 'frontend' esté en la raíz temporal
        return base / "frontend" / "dist"
    # En desarrollo, buscamos frontend/dist relativo a este archivo
    return base / "frontend" / "dist"


def _load_icons() -> dict[str, Image.Image]:
    """Carga iconos open/closed en PNG; si faltan usa fallback."""
    base = _base_path()
    
    # Normal icons (Blue)
    open_png = base / "icons" / "porticon.png"
    closed_png = base / "icons" / "porticonc.png"
    
    # Risk icons (Red)
    open_risk_png = base / "icons" / "porticonr.png"
    closed_risk_png = base / "icons" / "porticoncr.png"

    # Medium Risk icons (Orange)
    open_med_png = base / "icons" / "porticonm.png"
    closed_med_png = base / "icons" / "porticoncm.png"

    icons: dict[str, Image.Image] = {}
    
    def load_or_none(path):
        if path.exists():
            try:
                return Image.open(path)
            except Exception:
                pass
        return None

    icons["open"] = load_or_none(open_png)
    icons["closed"] = load_or_none(closed_png)
    icons["open_risk"] = load_or_none(open_risk_png)
    icons["closed_risk"] = load_or_none(closed_risk_png)
    icons["open_med"] = load_or_none(open_med_png)
    icons["closed_med"] = load_or_none(closed_med_png)

    # Fallback generator
    def create_icon(color_main, color_bg):
        try:
            size = 32
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse((2, 2, size - 2, size - 2), fill=color_main)
            draw.rectangle((9, 9, size - 9, size - 2), fill=color_bg)
            draw.rectangle((9, 14, size - 9, 19), fill=color_main)
            return img
        except Exception:
            return None

    # Blue (Normal)
    if not icons.get("open"):
        icons["open"] = create_icon((17, 110, 228, 255), (255, 255, 255, 230))
    if not icons.get("closed"):
        icons["closed"] = create_icon((17, 110, 228, 255), (255, 255, 255, 230))

    # Red (High Risk)
    if not icons.get("open_risk"):
        icons["open_risk"] = create_icon((220, 38, 38, 255), (255, 255, 255, 230)) # Red-600
    if not icons.get("closed_risk"):
        icons["closed_risk"] = create_icon((220, 38, 38, 255), (255, 255, 255, 230))

    # Orange (Medium Risk)
    if not icons.get("open_med"):
        icons["open_med"] = create_icon((245, 158, 11, 255), (255, 255, 255, 230)) # Amber-500
    if not icons.get("closed_med"):
        icons["closed_med"] = create_icon((245, 158, 11, 255), (255, 255, 255, 230))

    logging.info("Icons loaded: %s", list(icons.keys()))
    return icons


def _elevate_privileges() -> bool:
    """
    Intenta relanzar la aplicación con permisos de administrador usando osascript.
    Retorna True si se debe salir (porque se lanzó el proceso hijo exitosamente),
    False si se debe continuar (ya somos root, no es mac, o falló/canceló).
    """
    # Solo aplicar en macOS y si estamos empaquetados (frozen)
    if sys.platform != "darwin" or not getattr(sys, "frozen", False):
        return False

    # Si ya somos root, continuar normal
    if os.geteuid() == 0:
        return False

    executable = sys.executable
    logging.info("Intentando elevar privilegios para: %s", executable)

    # Script de AppleScript para lanzar con admin privileges
    # 'do shell script' espera hasta que el comando termine.
    # Para evitar bloquear este proceso mientras el otro corre, usamos '&' 
    # pero do shell script con admin privileges y background es tricky.
    # Mejor estrategia: lanzar y si no da error, asumir que el usuario puso pass y salir.
    # El 'do shell script' bloqueará este proceso hasta que el hijo termine.
    # Pero queremos que este proceso termine para que quede solo el root.
    # TRUCO: Usar ' &> /dev/null & ' dentro del string de shell para desvincularlo.
    
    script = f'''
    try
        do shell script "\\"{executable}\\" > /dev/null 2>&1 &" with administrator privileges
    on error
        return "CANCELLED"
    end try
    '''

    try:
        result = subprocess.check_output(['osascript', '-e', script], text=True).strip()
        if result == "CANCELLED":
            logging.warning("Usuario canceló la elevación de privilegios.")
            return False  # Continuar sin permisos
        
        # Si llegamos aquí, el comando se lanzó exitosamente en background (o eso esperamos)
        logging.info("Relanzado con permisos. Saliendo del proceso actual.")
        return True
    except Exception as e:
        logging.error("Error al intentar elevar privilegios: %s", e)
        return False



def trigger_alarm(risk_level: str = "medio"):
    """
    Play sound and focus window to alert user.
    This is the core "In-Your-Face" alert strategy.
    """
    try:
        # 1. Play Sound
        # Use 'Glass' for high risk (sharper), 'Ping' for others
        sound = "Glass" if risk_level == "alto" else "Ping"
        subprocess.run(["afplay", f"/System/Library/Sounds/{sound}.aiff"], check=False)
        
        # 2. Focus Window
        # This brings the browser window to the front
        # We reuse the smart_open_browser logic but just to focus
        # We need to know the URL, which is available in main() scope
        # Ideally we'd pass it, but for now we can rely on the fact that
        # smart_open_browser(url) handles focus if tab exists.
        pass # Handled in the loop by calling smart_open_browser
        
    except Exception as e:
        logging.error(f"Error triggering alarm: {e}")


def main():
    _setup_logging()
    
    # Intentar auto-elevación al inicio
    if _elevate_privileges():
        sys.exit(0)

    runner: ServerRunner | None = None
    port: int | None = None
    url: str = ""
    icons = _load_icons()
    stop_blink = threading.Event()

    def start_server():
        nonlocal runner, port, url
        if runner:
            runner.stop()
        port = _choose_port()
        url = f"http://{HOST}:{port}"
        runner = ServerRunner(HOST, port)
        runner.start()
        _wait_until_up(HOST, port, timeout=8)

    start_server()

    def smart_open_browser(url):
        """Open URL in browser, reusing existing tab if possible (macOS only)."""
        if sys.platform != 'darwin':
            # Fallback to regular webbrowser.open on non-macOS
            webbrowser.open(url)
            return
        
        # Try to find and focus existing tab in Safari/Chrome
        applescript = f'''
        set browserApps to {{"Google Chrome", "Safari", "Brave Browser", "Arc"}}
        
        tell application "System Events"
            set runningBrowsers to {{}}
            repeat with appName in browserApps
                if exists process appName then
                    set end of runningBrowsers to contents of appName
                end if
            end repeat
        end tell
        
        repeat with browserName in runningBrowsers
            tell application browserName
                try
                    set winList to every window
                    repeat with w in winList
                        set tabList to every tab of w
                        repeat with t in tabList
                            set tabUrl to URL of t
                            if tabUrl contains "127.0.0.1" or tabUrl contains "localhost" then
                                -- Found it! Focus it.
                                try
                                    if browserName as string is "Safari" then
                                        set current tab of w to t
                                    else
                                        set active tab index of w to (index of t)
                                    end if
                                    set index of w to 1
                                    activate
                                    return "true"
                                end try
                            end if
                        end repeat
                    end repeat
                on error
                    -- Ignore errors (e.g. browser doesn't support AppleScript suite)
                end try
            end tell
        end repeat
        return "false"
        '''
        
        try:
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            # If AppleScript found and focused the tab, we're done
            if result.returncode == 0 and 'true' in result.stdout:
                logging.info("Reused existing browser tab")
                return
        except Exception as e:
            logging.warning(f"AppleScript failed, falling back to webbrowser.open: {e}")
        
        # Fallback: open new tab
        webbrowser.open(url)

    def open_ui(icon, item=None):
        smart_open_browser(url)

    def restart(icon, item):
        start_server()
        smart_open_browser(url)

    def quit_app(icon, item):
        icon.visible = False
        if runner:
            runner.stop()
        stop_blink.set()
        icon.stop()

    def setup(icon):
        # Set icon inicial y lanza parpadeo
        icon.icon = icons.get("open") or icons.get("closed")
        icon.visible = True

        def _monitor_loop():
            """
            Monitors for alerts and handles blinking + sound/focus
            """
            logging.info("Monitor loop started")
            if not icons.get("open") or not icons.get("closed"):
                logging.warning("Icons not loaded, monitor loop might behave oddly")
                return
            
            last_alert_count = 0
            
            # Debug: Check if alert mode is enabled globally
            logging.info(f"ALERT_MODE_ENABLED status: {server.ALERT_MODE_ENABLED}")
            
            while not stop_blink.wait(random.uniform(2.0, 4.0)): # Faster check (2-4s)
                # Check risk level & pending alerts
                risk_level = "bajo"
                current_alert_count = 0
                has_new_alert = False
                
                try:
                    # 1. Check Pending Alerts (Priority)
                    # Access alert engine directly from server module
                    if server.ALERT_MODE_ENABLED:
                        pending = server.alert_engine.get_pending_alerts()
                        current_alert_count = len(pending)
                        
                        # Log only if there are alerts or status changes to avoid spam
                        if current_alert_count > 0:
                            logging.info(f"Monitor: Found {current_alert_count} pending alerts. Last count: {last_alert_count}")
                        
                        # Detect if we have NEW alerts
                        if current_alert_count > last_alert_count:
                            has_new_alert = True
                            logging.info(f"Monitor: NEW ALERT DETECTED! ({current_alert_count} > {last_alert_count})")
                            # Determine max risk of new alerts
                            risk_level = "alto" # Force high attention for new alerts
                            
                        last_alert_count = current_alert_count
                        
                        # If there are pending alerts, keep icon red/blinking
                        if current_alert_count > 0:
                            risk_level = "alto"
                    else:
                        # Log periodically if disabled (every ~100 checks or just once)
                        pass

                    # 2. Check Connections (Secondary)
                    if risk_level == "bajo":
                        # Access server connections safely
                        for conn in list(server.CONNECTIONS.values()):
                            lvl = conn.get("level")
                            if lvl == "alto":
                                risk_level = "alto"
                                break
                            elif lvl == "medio":
                                risk_level = "medio"
                
                except Exception as e:
                    logging.error(f"Error checking risk: {e}")

                # --- ACTION: TRIGGER ALARM ---
                if has_new_alert:
                    logging.info(f"🚨 TRIGGERING ALARM! Level: {risk_level}")
                    trigger_alarm(risk_level)
                    smart_open_browser(url) # FOCUS WINDOW
                
                # --- ICON UPDATE ---
                # Select icon set
                if risk_level == "alto":
                    icon_closed = icons.get("closed_risk") or icons.get("closed")
                    icon_open = icons.get("open_risk") or icons.get("open")
                elif risk_level == "medio":
                    icon_closed = icons.get("closed_med") or icons.get("closed")
                    icon_open = icons.get("open_med") or icons.get("open")
                else:
                    icon_closed = icons.get("closed")
                    icon_open = icons.get("open")

                # Blink logic
                icon.icon = icon_closed
                if stop_blink.wait(0.24):
                    break
                icon.icon = icon_open

        threading.Thread(target=_monitor_loop, daemon=True).start()

    menu = pystray.Menu(
        pystray.MenuItem("Abrir PortWatch", open_ui, default=True),
        pystray.MenuItem("Reiniciar servidor", restart),
        pystray.MenuItem("Salir", quit_app),
    )

    icon = pystray.Icon("PortWatch", icons.get("open") or icons.get("closed"), "PortWatch", menu)
    try:
        icon.run(setup=setup)
    except Exception:
        logging.exception("Error en tray_app, saliendo")
        raise


if __name__ == "__main__":
    main()

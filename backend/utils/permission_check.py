#!/usr/bin/env python3
"""
Modified tray_app.py that detects if running without root and shows a helpful message
"""
import os
import sys
import logging
from pathlib import Path

def check_root_access():
    """Check if we have root access for psutil.net_connections()"""
    try:
        import psutil
        # Try to get network connections
        conns = psutil.net_connections(kind='inet')
        return True  # If we got here, we have root access
    except (PermissionError, OSError):
        return False

def show_permission_dialog():
    """Show a dialog explaining the app needs permissions"""
    import subprocess
    script = '''
    display dialog "PortWatch necesita permisos de administrador para monitorear todas las conexiones de red.

Para ejecutar PortWatch con permisos completos:

1. Abre Terminal
2. Ejecuta: sudo /Applications/PortWatch.app/Contents/MacOS/PortWatch

O usa el script 'launch_portwatch.sh' incluido que pedirá la contraseña automáticamente." buttons {"Continuar sin permisos", "Salir"} default button "Salir" with title "PortWatch - Permisos Requeridos" with icon caution
    '''
    try:
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        # If user clicked "Continuar sin permisos", button returned is "Continuar sin permisos"
        return "Continuar sin permisos" in result.stdout
    except Exception:
        # If dialog fails, just continue
        return True

# This would be inserted at the start of main() in tray_app.py
def check_permissions_and_warn():
    """Check permissions and warn user if needed"""
    if not check_root_access():
        logging.warning("⚠️  PortWatch está ejecutándose sin permisos de administrador")
        logging.warning("    Solo verás conexiones limitadas")
        logging.warning("    Para funcionalidad completa, ejecuta con sudo")
        
        # Only show dialog if not in a terminal (GUI mode)
        if not sys.stdout.isatty():
            should_continue = show_permission_dialog()
            if not should_continue:
                sys.exit(0)
    else:
        logging.info("✓ PortWatch ejecutándose con permisos completos")

if __name__ == "__main__":
    check_permissions_and_warn()

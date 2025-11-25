#!/bin/bash
# First-run notification setup script for PortWatch

# Check if this is first run
FIRST_RUN_MARKER="$HOME/.portwatch/.notif_setup_done"

if [ ! -f "$FIRST_RUN_MARKER" ]; then
    # Show dialog explaining permissions
    osascript -e 'display dialog "PortWatch necesita permisos para enviarte notificaciones de seguridad.

Haz click en OK para abrir Configuración del Sistema donde debes:

1. Buscar \"PortWatch\" en la lista
2. Activar \"Permitir notificaciones\"
3. Seleccionar estilo: \"Avisos\" o \"Alertas\"

¿Quieres abrir Configuración del Sistema ahora?" buttons {"Más Tarde", "Abrir Configuración"} default button "Abrir Configuración" with icon note with title "PortWatch - Configuración Inicial"'
    
    RESPONSE=$?
    
    # If user clicked "Open Settings" (button 2)
    if [ $RESPONSE -eq 0 ]; then
        # Open System Preferences > Notifications
        open "x-apple.systempreferences:com.apple.preference.notifications"
        sleep 2
        # Try to focus on PortWatch entry (best effort)
        osascript -e 'tell application "System Preferences"
            activate
        end tell' 2>/dev/null
    fi
    
    # Mark as setup complete
    mkdir -p "$HOME/.portwatch"
    touch "$FIRST_RUN_MARKER"
fi

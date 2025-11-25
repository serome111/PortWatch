#!/bin/bash
# Script mejorado que actualiza build_app.sh para crear un launcher automático

cat &lt;&lt;'EOF' &gt; launch_with_permissions.sh
#!/bin/bash
# Auto-generated launcher for PortWatch
# This script requests administrator privileges and launches PortWatch

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &amp;&amp; pwd )"
PORTWATCH_BIN="$SCRIPT_DIR/PortWatch"

# Check if already running as root
if [ "$EUID" -eq 0 ]; then
    # Already root, just run
    exec "$PORTWATCH_BIN"
else
    # Not root, request privileges with native dialog
    osascript -e "do shell script \"'$PORTWATCH_BIN'\" with administrator privileges"
fi
EOF

chmod +x launch_with_permissions.sh
echo "✓ Launcher script created"

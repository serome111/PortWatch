#!/bin/bash
# Demo script para probar el Modo de Alerta Interactiva

echo "=========================================="
echo "PortWatch - Alert Mode Demo"
echo "=========================================="
echo ""
echo "Este script te ayudará a probar el sistema de alertas."
echo ""

# Check if server is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ El servidor no está corriendo."
    echo ""
    echo "Inicia el servidor primero:"
    echo "  uvicorn server:app --reload"
    echo ""
    exit 1
fi

echo "✓ Servidor corriendo"
echo ""

# Step 1: Check alert settings
echo "1. Configuración actual de alertas:"
echo "-----------------------------------"
curl -s http://localhost:8000/api/alerts/settings | python3 -m json.tool
echo ""

# Step 2: Check existing rules
echo "2. Reglas existentes:"
echo "-----------------------------------"
curl -s http://localhost:8000/api/rules | python3 -m json.tool
echo ""

# Step 3: Show pending alerts
echo "3. Alertas pendientes:"
echo "-----------------------------------"
curl -s http://localhost:8000/api/alerts/pending | python3 -m json.tool
echo ""

echo "=========================================="
echo "Cómo probar las alertas:"
echo "=========================================="
echo ""
echo "1. NOTIFICACIONES:"
echo "   python3 demo_alerts.py"
echo "   (Verás 3 notificaciones del sistema)"
echo ""
echo "2. CONEXIONES REALES:"
echo "   - Abre el browser en http://localhost:5173"
echo "   - Haz una conexión nueva (ej. visita github.com)"
echo "   - Deberías ver una notificación si es primera vez"
echo ""
echo "3. CREAR REGLA:"
echo "   curl -X POST http://localhost:8000/api/rules \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{
echo "       \"process\": \"Chrome\",
echo "       \"destination\": \"github.com\",
echo "       \"port\": 443,
echo "       \"action\": \"allow\",
echo "       \"scope\": \"always\"
echo "     }'"
echo ""
echo "4. CONFIGURAR ALERTAS:"
echo "   curl -X POST http://localhost:8000/api/alerts/settings \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{
echo "       \"enabled\": true,
echo "       \"alert_level\": \"medium\",
echo "       \"auto_allow_signed\": true
echo "     }'"
echo ""
echo "=========================================="
echo "Notas:"
echo "=========================================="
echo ""
echo "- Las notificaciones aparecen SOLO para conexiones NUEVAS"
echo "- Una conexión es \"nueva\" si es la primera vez que (app + destino + puerto) se conectan"
echo "- Puedes configurar el nivel de alerta: 'all', 'medium', 'high'"
echo "- Auto-allow para apps firmadas de Apple está activado por defecto"
echo ""

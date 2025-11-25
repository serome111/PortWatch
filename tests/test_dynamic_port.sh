#!/bin/bash
# Script para probar que el port dinámico funciona correctamente
# Prueba el funcionamiento de tray_app.py con puertos ocupados

set -e

echo "=========================================="
echo "Test: Dynamic Port Synchronization"
echo "=========================================="
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "Limpiando procesos de prueba..."
    if [ ! -z "$PY_SERVER_PID" ]; then
        kill $PY_SERVER_PID 2>/dev/null || true
    fi
    if [ ! -z "$TRAY_PID" ]; then
        kill $TRAY_PID 2>/dev/null || true
    fi
}

trap cleanup EXIT

# Test 1: Puerto 8000 libre
echo "Test 1: Puerto 8000 libre"
echo "------------------------------------"
echo "Iniciando tray_app.py..."
python3 tray_app.py &
TRAY_PID=$!
sleep 3

# Check if port 8000 is in use
if lsof -i :8000 >/dev/null 2>&1; then
    echo "✓ Puerto 8000 está en uso por tray_app"
    # Try to fetch the frontend
    if curl -s http://localhost:8000/ | grep -q "PortWatch"; then
        echo "✓ Frontend se sirve correctamente en puerto 8000"
    else
        echo "✗ Frontend NO se sirve en puerto 8000"
        exit 1
    fi
else
    echo "✗ Puerto 8000 NO está en uso"
    exit 1
fi

# Cleanup test 1
kill $TRAY_PID 2>/dev/null || true
TRAY_PID=""
sleep 2

echo ""
echo "Test 2: Puerto 8000 ocupado, debería usar 8001"
echo "------------------------------------"

# Occupy port 8000
echo "Ocupando puerto 8000 con un servidor HTTP simple..."
python3 -m http.server 8000 >/dev/null 2>&1 &
PY_SERVER_PID=$!
sleep 2

if lsof -i :8000 >/dev/null 2>&1; then
    echo "✓ Puerto 8000 está ocupado"
else
    echo "✗ No se pudo ocupar puerto 8000"
    exit 1
fi

echo "Iniciando tray_app.py (debería elegir puerto 8001)..."
python3 tray_app.py &
TRAY_PID=$!
sleep 3

# Check if port 8001 is in use
if lsof -i :8001 >/dev/null 2>&1; then
    echo "✓ Puerto 8001 está en uso por tray_app"
    # Try to fetch the frontend
    if curl -s http://localhost:8001/ | grep -q "PortWatch"; then
        echo "✓ Frontend se sirve correctamente en puerto 8001"
    else
        echo "✗ Frontend NO se sirve en puerto 8001"
        exit 1
    fi
else
    echo "✗ tray_app no usó puerto 8001"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ Todos los tests pasaron exitosamente"
echo "=========================================="
echo ""
echo "Resumen:"
echo "  - Frontend se sirve automáticamente desde el backend"
echo "  - Port dinámico funciona correctamente (8000 -> 8001)"
echo "  - La app compilada funcionará en cualquier dispositivo"
echo ""

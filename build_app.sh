#!/usr/bin/env bash
# Helper para empaquetar PortWatch con PyInstaller usando pip (sin uv).
# Uso:
#   ./build_app_pip.sh            # autodetecta macOS/Linux
#   ./build_app_pip.sh mac        # fuerza macOS
#   ./build_app_pip.sh linux      # fuerza Linux

set -euo pipefail

PLATFORM="${1:-auto}"

# Verificar python3 y pip
if ! command -v python3 >/dev/null 2>&1; then
  echo "Falta 'python3'. Por favor instálalo." >&2
  exit 1
fi

if [[ "${PLATFORM}" == "auto" ]]; then
  uname_s="$(uname -s | tr '[:upper:]' '[:lower:]')"
  if [[ "${uname_s}" == "darwin" ]]; then
    PLATFORM="mac"
  else
    PLATFORM="linux"
  fi
fi

if [[ "${PLATFORM}" != "mac" && "${PLATFORM}" != "linux" ]]; then
  echo "Plataforma no reconocida: ${PLATFORM} (usa mac|linux|auto)" >&2
  exit 1
fi

# ========================================
# LIMPIEZA COMPLETA
# ========================================
echo "🧹 Limpiando compilaciones anteriores..."

# Mata instancias viejas de PortWatch
if [[ "${PLATFORM}" == "mac" ]]; then
  echo "   → Deteniendo instancias de PortWatch..."
  killall PortWatch 2>/dev/null || true
  sleep 1
fi

# Elimina directorios de build
echo "   → Eliminando build/, dist/, __pycache__..."
rm -rf build/ dist/ __pycache__/
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Limpia frontend
echo "   → Eliminando frontend/dist/..."
rm -rf frontend/dist/

echo "✅ Limpieza completa"
echo ""

# ========================================
# PREPARACIÓN DE ENTORNO VIRTUAL
# ========================================
echo "🛠️  Creando entorno virtual temporal para el build..."
VENV_DIR=".build_venv"
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

# Asegura dependencias en el venv
echo "📦 Instalando dependencias en entorno virtual..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Build Frontend
echo "Construyendo frontend..."
cd frontend
if [[ ! -d "node_modules" ]]; then
  npm install --legacy-peer-deps
fi
npm run build
cd ..

# Iconos
ICON_PNG="icons/Desktop.png"
ICON_ICNS="icons/Desktop.icns"
ICON_FLAG=""

if [[ -f "${ICON_ICNS}" ]]; then
  ICON_FLAG="--icon ${ICON_ICNS}"
elif [[ -f "${ICON_PNG}" ]]; then
  ICON_FLAG="--icon ${ICON_PNG}"
fi

if [[ "${PLATFORM}" == "mac" ]]; then
  echo "📦 Empaquetando PortWatch.app para macOS..."
  # Usamos 'pyinstaller' directo del venv
  pyinstaller backend/ui/tray_app.py \
    --name PortWatch \
    --windowed \
    --add-data "frontend/dist:frontend/dist" \
    --add-data "icons:icons" \
    --hidden-import backend.core.server \
    --hidden-import backend.core.alert_engine \
    --hidden-import backend.core.rules_manager \
    --hidden-import backend.utils.dns_sniffer \
    --hidden-import backend.utils.dns_analyzer \
    --hidden-import backend.utils.notifier \
    --hidden-import backend.utils.permission_check \
    --collect-all jaraco \
    --hidden-import platformdirs \
    ${ICON_FLAG}

  # Limpieza de artefactos intermedios
  echo "🧹 Limpiando archivos temporales de build..."
  rm -rf dist/PortWatch build/ PortWatch.spec
  
  # Limpieza del venv
  deactivate
  rm -rf "${VENV_DIR}"
  
  echo ""
  echo "✅ Build completado exitosamente!"
  echo "📂 Ubicación: dist/PortWatch.app"
  echo ""
  echo "🚀 Abriendo aplicación..."
  sleep 1
  open dist/PortWatch.app
  echo ""
  echo "✨ PortWatch iniciado. ¡Disfruta!"
else
  echo "📦 Empaquetando portwatch-tray (Linux)..."
  # Usamos 'pyinstaller' directo del venv
  pyinstaller backend/ui/tray_app.py \
    --onefile \
    --name portwatch-tray \
    --add-data "frontend/dist:frontend/dist" \
    --add-data "icons:icons" \
    --hidden-import backend.core.server \
    --hidden-import backend.core.alert_engine \
    --hidden-import backend.core.rules_manager \
    --hidden-import backend.utils.dns_sniffer \
    --hidden-import backend.utils.dns_analyzer \
    --hidden-import backend.utils.notifier \
    --hidden-import backend.utils.permission_check \
    ${ICON_FLAG}

  # Limpieza de artefactos intermedios
  echo "🧹 Limpiando archivos temporales de build..."
  rm -rf build/ portwatch-tray.spec
  
  # Limpieza del venv
  deactivate
  rm -rf "${VENV_DIR}"
  
  echo ""
  echo "✅ Build completado exitosamente!"
  echo "📂 Ubicación: dist/portwatch-tray"
  echo ""
  echo "Para ejecutar: ./dist/portwatch-tray"
fi

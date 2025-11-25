# PortWatch Tests

Este directorio contiene scripts de prueba, diagnóstico y simulación para PortWatch.

## Quick Start

```bash
# Verificar estado del sistema
python tests/check_status.py

# Diagnosticar sistema de alertas
python tests/diagnose_alerts.py

# Test de GeoIP
python tests/test_geoip.py
```

## Tests Funcionales

### `test_alert_mode.py`
Prueba el sistema de alertas interactivas.
```bash
python tests/test_alert_mode.py
```

### `test_alert_integration.sh`
Test de integración completo del sistema de alertas.
```bash
bash tests/test_alert_integration.sh
```

### `test_strict_alerting.py`
Verifica el modo de alerta estricto.
```bash
python tests/test_strict_alerting.py
```

### `test_rule_persistence.py`
Verifica la persistencia de reglas de firewall en SQLite.
```bash
python tests/test_rule_persistence.py
```

### `test_resource_alert.py`
Prueba alertas basadas en uso de recursos (CPU, RAM, disco).
```bash
python tests/test_resource_alert.py
```

### `test_geoip.py`
Verifica funcionalidad de geolocalización de IPs.
```bash
python tests/test_geoip.py
```

### `test_notifications.py`
Prueba el sistema de notificaciones nativas de macOS.
```bash
python tests/test_notifications.py
```

### `test_icons.py`
Verifica renderizado de iconos en la aplicación.
```bash
python tests/test_icons.py
```

### `test_tray_setup.py`
Prueba inicialización del icono de bandeja del sistema.
```bash
python tests/test_tray_setup.py
```

### `test_dynamic_port.sh`
Prueba asignación dinámica de puertos del servidor.
```bash
bash tests/test_dynamic_port.sh
```

## Simulación y Verificación

### `simulate_ransomware.py`
Simula comportamiento de ransomware para testing.

⚠️ **ADVERTENCIA:** Crea un archivo grande (`ransomware_sim.tmp`) y consume recursos. Solo para pruebas.

```bash
python tests/simulate_ransomware.py
```

### `verify_ransomware_detection.py`
Verifica detección de comportamiento de ransomware.
```bash
# Terminal 1:
python tests/simulate_ransomware.py

# Terminal 2:
python tests/verify_ransomware_detection.py
```

### `demo_alerts.py`
Demostración interactiva del sistema de alertas.
```bash
python tests/demo_alerts.py
```

### `trigger_alert.py`
Dispara una alerta de prueba simple.
```bash
python tests/trigger_alert.py
```

## Utilidades de Diagnóstico

### `check_status.py`
Muestra estado general de PortWatch (servidor, configuración, procesos).
```bash
python tests/check_status.py
```

### `diagnose_alerts.py`
Diagnóstico comprehensivo del sistema de alertas (configuración, permisos, estado).
```bash
python tests/diagnose_alerts.py
```

### `clear_alert_cache.py`
Limpia el caché de alertas vistas (útil durante desarrollo).
```bash
python tests/clear_alert_cache.py
```

## Workflow de Testing Recomendado

1. **Estado General:** `check_status.py` - Verificar estado del sistema
2. **Alertas Básicas:** `test_alert_mode.py` - Sistema de alertas
3. **Recursos:** `test_resource_alert.py` - Monitoreo de recursos
4. **Ransomware:** `simulate_ransomware.py` + `verify_ransomware_detection.py` - Heurísticas
5. **Integración:** `test_alert_integration.sh` - Prueba end-to-end completa

## Notas Importantes

- **Permisos:** Algunos tests requieren permisos especiales en macOS (notificaciones, red)
- **Entorno:** Ejecutar desde el directorio raíz del proyecto
- **Python:** Requiere Python 3.11+
- **Dependencias:** Activar venv e instalar dependencias antes de ejecutar tests

## Troubleshooting

Si encuentras problemas:

1. Verifica que el servidor esté corriendo
2. Verifica permisos de notificaciones en Preferencias del Sistema → Notificaciones
3. Revisa los logs del servidor
4. Ejecuta `diagnose_alerts.py` para un diagnóstico completo

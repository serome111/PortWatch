#!/usr/bin/env python3
"""
Quick diagnostic - Check current state after activation
"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("\n" + "="*70)
print("DIAGNÓSTICO RÁPIDO - Estado Actual")
print("="*70)

# 1. Check alert settings
try:
    response = requests.get(f"{BASE_URL}/api/alerts/debug")
    data = response.json()
    
    print("\n1️⃣  CONFIGURACIÓN DE ALERTAS:")
    if data.get("ok"):
        settings = data['settings']
        enabled = settings.get('enabled')
        level = settings.get('alert_level')
        auto_allow = settings.get('auto_allow_signed')
        
        print(f"   Modo Alertas: {'✅ ACTIVADO' if enabled else '❌ DESACTIVADO'}")
        print(f"   Nivel: {level}")
        print(f"   Auto-permitir Apple: {'✅ Sí' if auto_allow else '❌ No'}")
        print(f"   Conexiones vistas: {data.get('seen_connections_count', 0)}")
        print(f"   Alertas pendientes: {data.get('pending_alerts_count', 0)}")
        
        if not enabled:
            print("\n   ⚠️  PROBLEMA: Modo de alertas sigue DESACTIVADO")
            print("   → Verifica que guardaste después de activar el toggle")
        
        if data.get('pending_alerts'):
            print(f"\n   🔔 Hay {len(data['pending_alerts'])} alerta(s) pendiente(s):")
            for alert in data['pending_alerts']:
                conn = alert.get('connection', {})
                print(f"      • {conn.get('proc', 'unknown')} -> {conn.get('raddr', 'unknown')}")
                print(f"        Nivel: {conn.get('level', 'unknown')}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*70)
print("2️⃣  ACCIONES NECESARIAS:")
print("="*70)

print("""
Por favor, proporciona la siguiente información:

A. LOGS DEL SERVIDOR:
   - Ve a la terminal donde está corriendo 'python3 server.py'
   - Copia las ÚLTIMAS 30 LÍNEAS de log
   - Busca específicamente mensajes que contengan:
     * "Processing connection:"
     * "Evaluating"
     * "New connection detected"
     * "should_alert"
     * "Created pending alert"

B. INFORMACIÓN DEL PROGRAMA:
   1. ¿Qué programa ejecutaste?
   2. ¿Lo ves en la tabla "Conexiones Activas"? (Sí/No)
   3. Si está en la tabla:
      - ¿Qué dice en la columna "Nivel"? (verde BAJO / amarillo MEDIO / rojo ALTO)
      - ¿Qué dice en la columna "Score"? (número)
      - ¿Tiene algún badge en "Evidencia"?

C. NAVEGADOR:
   1. ¿Tienes PortWatch abierto en http://localhost:8000? (Sí/No)
   2. Abre la consola del navegador (F12 o Cmd+Opt+I)
   3. ¿Ves algún error en rojo?

D. PRUEBA MANUAL:
   Ejecuta esto en otra terminal:
   
   curl -X POST http://localhost:8000/api/alerts/test
   
   ¿Apareció la alerta con este comando? (Sí/No)
   Si NO apareció, hay un problema con las notificaciones del sistema.
""")

print("\n" + "="*70)
print("🔍 RECORDATORIO:")
print("="*70)
print("""
El sistema SOLO alerta sobre:
- Conexiones NUEVAS (que nunca ha visto antes)
- Con nivel MEDIO o ALTO (si configurado en "medium")
- Cuando el Modo de Alertas está ACTIVADO

Si la conexión:
- Ya existía antes → NO alerta (ya fue vista)
- Es de nivel BAJO → NO alerta (no cumple threshold)
- Apareció antes de activar el modo → NO alerta retroactivamente
""")

print("\n📋 Por favor copia y pega los logs del servidor aquí.\n")

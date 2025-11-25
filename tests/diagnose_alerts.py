#!/usr/bin/env python3
"""
Diagnóstico completo del sistema de alertas y notificaciones
"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("\n" + "="*70)
print("DIAGNÓSTICO COMPLETO - SISTEMA DE ALERTAS")
print("="*70)

# 1. Estado del Alert Engine
print("\n📊 1. CONFIGURACIÓN DEL ALERT ENGINE")
print("-" * 70)
try:
    response = requests.get(f"{BASE_URL}/api/alerts/debug")
    data = response.json()
    
    if data.get("ok"):
        settings = data['settings']
        
        print(f"Estado: {'✅ ACTIVO' if settings.get('enabled') else '❌ DESACTIVADO'}")
        print(f"Nivel: {settings.get('alert_level')}")
        print(f"Auto-permitir Apple: {'Sí' if settings.get('auto_allow_signed') else 'No'}")
        print(f"Cooldown: {settings.get('notification_cooldown')}s")
        print(f"\nConexiones vistas: {data.get('seen_connections_count', 0)}")
        print(f"Alertas pendientes: {data.get('pending_alerts_count', 0)}")
        
        if not settings.get('enabled'):
            print("\n⚠️  PROBLEMA: El modo de alertas está DESACTIVADO")
            print("   → No se generarán alertas aunque todo lo demás esté bien")
        
        if settings.get('alert_level') == 'high':
            print("\n⚠️  ADVERTENCIA: Nivel configurado en 'high'")
            print("   → Solo alertará conexiones de nivel ALTO")
            print("   → Conexiones de nivel MEDIO no alertarán")
        
        if data.get('pending_alerts'):
            print(f"\n🔔 ALERTAS PENDIENTES ({len(data['pending_alerts'])}):")
            for alert in data['pending_alerts']:
                conn = alert.get('connection', {})
                print(f"   • {conn.get('proc', 'unknown')} -> {conn.get('raddr', 'unknown')}")
                print(f"     Nivel: {conn.get('level', 'unknown')}")
        
    else:
        print(f"❌ Error: {data.get('error')}")
except Exception as e:
    print(f"❌ Error conectando: {e}")

# 2. Reglas activas
print("\n\n📋 2. REGLAS ACTIVAS")
print("-" * 70)
try:
    response = requests.get(f"{BASE_URL}/api/rules")
    data = response.json()
    
    if data.get("ok"):
        rules = data.get('rules', [])
        deny_rules = [r for r in rules if r['action'] == 'deny' and r['enabled']]
        allow_rules = [r for r in rules if r['action'] == 'allow' and r['enabled']]
        
        print(f"Total: {len(rules)} reglas")
        print(f"  - Deny (bloqueadas): {len(deny_rules)}")
        print(f"  - Allow (permitidas): {len(allow_rules)}")
        
        if deny_rules:
            print(f"\n🚫 REGLAS DE BLOQUEO:")
            for rule in deny_rules[:5]:  # Mostrar primeras 5
                print(f"   • {rule.get('process', 'unknown')} (scope: {rule.get('scope', 'unknown')})")
except Exception as e:
    print(f"❌ Error: {e}")

# 3. Notificaciones del Sistema
print("\n\n🔔 3. NOTIFICACIONES DEL SISTEMA")
print("-" * 70)
print("Probando capacidad de notificación...")

try:
    response = requests.post(f"{BASE_URL}/api/alerts/test")
    data = response.json()
    
    if data.get("ok"):
        print("✅ Solicitud de prueba enviada exitosamente")
        print("\n¿QUÉ DEBERÍAS VER AHORA?")
        print("   1. 🔊 Sonido de alerta")
        print("   2. 🪟 Ventana PortWatch al frente")
        print("   3. 🔔 Badge de alerta en el header")
        print("   4. 📋 Panel de alertas abierto")
        print("\n¿Viste/escuchaste todo esto? (Sí/No)")
    else:
        print(f"❌ Error en prueba: {data.get('error')}")
except Exception as e:
    print(f"❌ Error: {e}")

# 4. Resumen de posibles problemas
print("\n\n🔍 4. DIAGNÓSTICO DE PROBLEMAS COMUNES")
print("-" * 70)

try:
    response = requests.get(f"{BASE_URL}/api/alerts/debug")
    data = response.json()
    
    if data.get("ok"):
        settings = data['settings']
        seen_count = data.get('seen_connections_count', 0)
        
        issues = []
        
        # Check 1: Enabled
        if not settings.get('enabled'):
            issues.append({
                "nivel": "🔴 CRÍTICO",
                "problema": "Modo de alertas DESACTIVADO",
                "solución": "Ejecutar: python3 force_enable_alerts.py"
            })
        
        # Check 2: Level
        if settings.get('alert_level') == 'high':
            issues.append({
                "nivel": "🟡 ADVERTENCIA",
                "problema": "Nivel configurado en 'high' (solo alertas altas)",
                "solución": "Cambiar a 'medium' en Settings > Alertas > Nivel de Alerta"
            })
        
        # Check 3: Seen connections
        if seen_count > 50:
            issues.append({
                "nivel": "🟡 ADVERTENCIA",
                "problema": f"Cache grande ({seen_count} conexiones vistas)",
                "solución": "Las conexiones ya vistas no alertarán. Solución:\n" +
                           "            python3 clear_alert_cache.py\n" +
                           "            O reiniciar servidor"
            })
        
        # Check 4: Auto-allow
        if settings.get('auto_allow_signed'):
            issues.append({
                "nivel": "🔵 INFO",
                "problema": "Auto-permitir apps de Apple ACTIVADO",
                "solución": "Apps firmadas por Apple no generarán alertas.\n" +
                           "            Si quieres alertas de apps Apple, desactiva esto."
            })
        
        if not issues:
            print("✅ No se detectaron problemas de configuración")
            print("\nSi aún así no ves alertas:")
            print("  1. Verifica que el programa genera conexión de nivel MEDIO o ALTO")
            print("  2. Revisa los logs del servidor para ver si se procesa")
            print("  3. Asegúrate que es una conexión NUEVA (no vista antes)")
        else:
            print("Se detectaron los siguientes problemas:\n")
            for i, issue in enumerate(issues, 1):
                print(f"{i}. {issue['nivel']}: {issue['problema']}")
                print(f"   Solución: {issue['solución']}\n")

except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*70)
print("INSTRUCCIONES FINALES")
print("="*70)
print("""
Para que las alertas funcionen correctamente:

1. ✅ Modo de alertas: ACTIVADO
2. ✅ Nivel: 'medium' o 'all' (para ver alertas medias)
3. ✅ Conexión nueva (no vista antes)
4. ✅ Conexión de nivel medio o alto
5. ✅ PortWatch abierto en navegador
6. ✅ Permisos de notificación en macOS

Si cumples todo y no ves alertas:
→ Copia y pega los logs del servidor (últimas 30 líneas)
→ Dime qué programa ejecutaste
→ Dime si lo ves en la tabla de conexiones y qué nivel muestra
""")

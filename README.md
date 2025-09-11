# PortWatch

- Pregunta a resolver: “¿Estoy hackeado?”
Panel web para entender conexiones salientes en macOS por aplicación y priorizar riesgo con señales simples.

## Características clave
- Modo simple (por defecto): frases en lenguaje claro por cada conexión y tarjetas de resumen.
- Cola de revisiones: mantiene las sospechosas (medio/alto) aunque la conexión termine; puedes “Ver” o “Descartar”.
- Conexiones normales: lista plegable con explicación breve de por qué son normales.
- Histórico local (hoy): cuenta conexiones por app y destinos; persiste en `localStorage`.
- Vista técnica: tabla detallada por proceso con score 0–10, nivel, firma (Apple/tercero/sin firma), quarantine, laddr/raddr/puerto, servicio, destinos únicos, patrón repetitivo (beaconing) y botón “Plan”.
- Firmas y confianza: integra `codesign`, `spctl` y `xattr` para firma/notarización/quarantine (macOS).
- Servicio por puerto y detección de “servidor local”.
- Fallback a `lsof` si `psutil` no ve todo (macOS).
- Hints por puertos: minería (3333/4444) y Tor (9001–9030) aumentan el score y etiquetan el servicio.
- Chips de evidencia: etiquetas visibles para “/tmp”, puertos sensibles (ej. 22), IP pública, beaconing, sin firma, quarantine, minería/Tor.
- Edad del binario: si el ejecutable fue modificado en las últimas 72 h y se conecta a Internet, suma riesgo (“Binario reciente con salida”).
- Modo paranoico: botón rojo para mostrar acciones STOP/KILL por proceso sospechoso (requiere permisos/sudo para afectar procesos de otros usuarios).
  - Autokill: cuando el modo paranoico está ON, aplica automáticamente Kill (por defecto) o Stop a procesos de riesgo medio/alto. Se puede cambiar a Stop desde el selector junto al botón.

## Ejecutar
- Requisitos: Python 3.10+ (o superior)
- Instalar dependencias: `pip install -r requirements.txt`
- Iniciar servidor: `uvicorn server:app --reload`
- Abrir UI: `http://localhost:8000`
- Recomendado: iniciar con `sudo` para ver conexiones de todos los procesos y permitir rutas de ejecutables/firma.

## Uso rápido
- Botón “Opciones ▾”:
  - `Modo simple` (ON por defecto)
  - `Auto` (autorefresco cada 2s)
  - `Agrupar por servicio`, `Ocultar Apple`, `Solo no Apple`, `Solo ESTABLISHED`
- Modo simple:
  - “Conexiones a revisar”: sospechosas persistentes con “Ver” y “Descartar”.
  - “Conexiones normales”: plegable con frases claras.
  - “Histórico (hoy)”: top de apps y destinos (se borra con “Borrar”).
- Vista técnica: ordena por score; usa “Plan” para pasos de investigación/contención. Cada fila tiene “Exportar” (JSON/MD) para guardar evidencia local.

## API
- `/` — UI HTML
- `/api/connections` — JSON de conexiones actuales
  - Query: `source=auto|psutil|lsof`, `established_only=0|1`
- `/api/action_plan?pid=PID&raddr=IP:PUERTO` — pasos sugeridos
- `/api/export_case?pid=PID&raddr=IP:PUERTO&fmt=json|md` — exporta evidencia del caso (JSON o Markdown)
- `/api/proc_stop?pid=PID` — envía SIGSTOP (pausar)
- `/api/proc_kill?pid=PID` — envía SIGKILL (forzar fin)
- `/health` — ping

## Cómo interpretar el riesgo
- Bajo: apps de Apple/firmadas, sin repeticiones anormales, destinos habituales (p. ej. https/443).
- Medio: ejecutable en rutas de usuario, muchos destinos, IP pública, patrones repetitivos.
- Alto: sin firma/quarantine, rutas temporales (/tmp), puertos sensibles (22/23/25/445/3389/5900), beaconing claro.
  - También suma si usa puertos característicos: minería (3333/4444) o Tor (9001–9030).

## Solución de problemas
- No ves procesos del sistema: inicia con `sudo` y da “Full Disk Access” a tu terminal.
- La UI queda en “Cargando…”: recarga dura (Cmd/Ctrl+Shift+R). Si persiste, borra `localStorage.pwCfg` y `localStorage.pwHistory` desde la consola del navegador.
- macOS específico: verificación de firma/notarización/quarantine requiere utilidades nativas (`codesign`, `spctl`, `xattr`).

## Requerimientos
- GPU: ninguna.
- CPU: mínimo 1 núcleo; recomendado 2 núcleos.
- RAM: mínimo 256–512 MB libres; recomendado ≥1 GB libre.
- Disco: <100 MB (código + deps).
- SO: Python 3.10+ (macOS 12+ o Linux).

## Nota
Usa PortWatch en tu propio equipo y con fines legítimos. La información de “histórico” y “revisión” se guarda localmente en tu navegador (no sale de tu máquina).

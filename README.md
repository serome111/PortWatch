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
- Acciones de contención desde el modal “Ver” (sin activar modo paranoico):
  - `KILL (SIGKILL)` del PID seleccionado.
  - `Kill árbol (N)`: termina recursivamente al proceso y a sus N descendientes (solo se muestra si hay descendientes).
  - `Kill grupo (pgid X)`: termina todo el process group del PID (útil para scripts sh que relanzan hijos en bucle).
  - `Bootout <label>` (macOS): intenta descargar/deshabilitar el LaunchAgent/Daemon detectado con `launchctl` para que no se relance.
- Modo paranoico: botón rojo para mostrar acciones STOP/KILL en todas las filas (requiere permisos/sudo para afectar procesos de otros usuarios).
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
- `/api/proc_tree?pid=PID` — información de árbol: padres, `pgid`, `children_count` y (macOS) `launchd.label`/`domain`/`path` si se detecta
- `/api/proc_kill_tree?pid=PID` — mata recursivamente al proceso y todos sus hijos
- `/api/proc_kill_pgid?pid=PID` — mata todo el process group del PID (SIGKILL)
- `/api/proc_bootout?pid=PID` — macOS: intenta `launchctl bootout/disable/remove` para el label detectado
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
 - Alerta “¡HACKEADO!”: se muestra si hay sospechosas (medio/alto). Pulsa “Resolver” para ocultarla; volverá a aparecer cuando cambie el conjunto de hallazgos (nuevas sospechosas distintas).

### Procesos que “reviven” (scripts que relanzan hijos)
- Abre el modal “Ver” sobre la conexión sospechosa.
- Si aparece `Kill árbol (N)`, úsalo para terminar al proceso y sus descendientes.
- Si el proceso es lanzado por un script en bucle, usa `Kill grupo (pgid X)` para terminar el process group completo (incluye el script padre).
- Si el proceso proviene de `launchd` (macOS) y ves `Bootout <label>`, ejecútalo para descargar/deshabilitar el servicio. Para Daemons del sistema puede requerir `sudo`.
- Como contención adicional: `STOP` al script (pausar), renombrar o `chmod 000` el ejecutable/script y luego `KILL`.

### Auto vs psutil/lsof (macOS)
`psutil` puede no ver conexiones de otros procesos sin permisos elevados. Si “Auto” muestra menos de lo esperado, compara con `/api/connections?source=lsof&established_only=1`.

### Protección del propio servidor
Por defecto PortWatch no permite enviar señales a sí mismo ni a sus ancestros.
- Variable de entorno: `PW_PROTECT_SELF=1` (por defecto). Poner `PW_PROTECT_SELF=0` para desactivar la protección si realmente lo necesitas.

## Requerimientos
- GPU: ninguna.
- CPU: mínimo 1 núcleo; recomendado 2 núcleos.
- RAM: mínimo 256–512 MB libres; recomendado ≥1 GB libre.
- Disco: <100 MB (código + deps).
- SO: Python 3.10+ (macOS 12+ o Linux).

## Mejoras en revision
- Edad del binario: si mtime < 72h y conecta fuera → “binario reciente con salida”.
- Notificaciones del sistema: osascript display notification (mac) / notify-send (Linux) cuando aparezca alto nuevo.
- Reverse DNS + dominio raíz: mostrar rdns/eTLD+1 (p. ej. cdn.cloudflare.net → cloudflare.net) para contexto humano.
- “Primera vez hoy/semana”: badge si el destino/proceso es nuevo en la ventana temporal.(leer mas)
- Puertos atípicos por proceso: si un proceso que siempre usa 443 habla por 23/445 → etiqueta “puerto inusual”.
- Parent process heuristic: si ppid ∈ {bash, curl, sh} y el hijo conecta a IP pública → +razón “spawn sospechoso”. (leer mas)
- LISTEN expuesto: vista rápida de sockets LISTEN en 0.0.0.0/:: con puertos sensibles (servidor local accidental). (leer mas)
- IOC rápido: campo para pegar IP/DOMINIO/PUERTO → resalta coincidencias en la tabla (no requiere Internet).
- Lista blanca granular: “Confiar en (proc, hash, dest)” con TTL (p. ej. 7 días) para reducir ruido temporal.(leer mas)(o manual granular)
- Heurística extra simple: +1 si el ejecutable está en carpeta de usuario (~/Downloads, ~/Library) y conecta a IP pública.
- “Sospechoso por repetición”: badge cuando un mismo PID habla con ≥N IPs únicas en poco tiempo. (leer mas)
- Parent sospechoso: si ppid ∈ {bash, sh, curl} y el hijo conecta a IP pública ⇒ +razón “spawn inusual”.  (leer mas)
- Persistencia mínima (solo conteo): mostrar un contador rápido de hallazgos relacionados con el ejecutable del PID:
  macOS: ~/Library/LaunchAgents, /Library/LaunchDaemons, crontab -l.
  Linux: ~/.config/autostart, systemd --user, crontab -l.
  No ejecutes nada; solo “0/1/2 ítems encontrados” + rutas. Sube el veredicto si >0.
-
# Mejoras linux
- Tilt Linux/macOS: si no es macOS, desactiva penalizaciones de firma/quarantine (evita inflar score).

## Nota
Usa PortWatch en tu propio equipo y con fines legítimos. La información de “histórico” y “revisión” se guarda localmente en tu navegador (no sale de tu máquina).



## Archivo para pruebas.

chmod +x portwatch_make_suspicious.sh

# 1) Minero local (puerto 3333 + beaconing + binario en /tmp)
./portwatch_make_suspicious.sh miner

# 2) Beacon a IP pública (1.1.1.1:443)
./portwatch_make_suspicious.sh public

# 3) “Spray” (varios hosts para subir unique_dsts y empujar a Alto)
./portwatch_demo.sh spray

# 4) Parar y limpiar
./portwatch_demo.sh stop

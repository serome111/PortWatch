import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X, Shield, Globe, Activity, Server, AlertTriangle, Info, FileText, User, Network, Skull, Zap, Users } from 'lucide-react'
import { cn } from '../lib/utils'
import { ConfirmModal } from './ConfirmModal'
import { CopyButton } from './CopyButton'
import { ProcessIcon } from './ProcessIcon'
import { useTranslation } from 'react-i18next'

export function ConnectionDetailsModal({ connection, onClose }) {
    const { t } = useTranslation()
    const [processInfo, setProcessInfo] = useState(null)
    const [loading, setLoading] = useState(false)
    const [confirmDialog, setConfirmDialog] = useState(null) // { title, message, onConfirm, danger }


    useEffect(() => {
        if (!connection) return

        // Fetch process tree info for advanced actions
        const fetchProcessInfo = async () => {
            try {
                const res = await fetch(`/api/proc_tree?pid=${connection.pid}`)
                const data = await res.json()
                setProcessInfo(data)
            } catch (err) {
                console.error('Error fetching process tree:', err)
            }
        }

        fetchProcessInfo()
    }, [connection])

    if (!connection) return null

    // Helper para tipo de IP (basado en el HTML anterior)
    const getIpType = (host) => {
        if (!host) return 'desconocido'
        if (host.startsWith('127.') || host === '::1') return 'tu Mac'
        if (host.startsWith('10.') || host.startsWith('192.168.') || /^172\.(1[6-9]|2\d|3[01])\./.test(host)) return 'tu red local'
        return 'Internet'
    }

    // Helper para detectar si parece un servidor local
    const hostFrom = (addr) => (addr || '').split(':')[0] || ''
    const portFrom = (addr) => {
        const p = (addr || '').split(':').pop()
        const n = Number(p)
        return Number.isFinite(n) ? n : null
    }

    const TYPICAL_SERVER_PORTS = new Set([80, 443, 8000, 8080, 3000, 5000, 8888, 27017, 6379, 5432, 3306, 22, 5900])

    const seemsServerLocal = (conn) => {
        const lh = hostFrom(conn.laddr)
        const lp = portFrom(conn.laddr)
        const ipType = getIpType(lh)
        return (lp && (lp <= 1024 || TYPICAL_SERVER_PORTS.has(lp))) && (ipType !== 'Internet')
    }

    // Generar narrativa basada en evidencia (Storytelling)
    const getNarrative = (conn) => {
        const proc = conn.proc || conn.name || 'Este proceso'
        const isUnsigned = !conn.signed && !conn.apple
        const isApple = conn.apple
        const isTor = (conn.service === 'tor' || (conn.reasons || []).some(r => r.includes('Tor')))
        const isMining = (conn.service === 'mining-stratum' || (conn.reasons || []).some(r => r.includes('minería')))
        const isBeacon = conn.beacon
        const isHighRes = (conn.cpu > 50 || conn.mem > 500 * 1024 * 1024)
        const isPublic = getIpType(hostFrom(conn.raddr)) === 'Internet'
        const isTmp = (conn.exe || '').includes('/tmp') || (conn.exe || '').includes('/var/tmp')
        const dnsRisk = conn.dns_risk

        // 0. COMPOSITE: Mining + Tor (Highest Priority)
        if (isMining && isTor) {
            return t('narratives.mining_tor', { proc })
        }

        // 0. COMPOSITE: C2 Beacon (Malicious Domain + Beacon)
        if (dnsRisk && dnsRisk.score > 50 && isBeacon) {
            return t('narratives.c2_beacon', { proc })
        }

        // 0. COMPOSITE: Dropper (Unsigned + Tmp)
        if (isUnsigned && isTmp) {
            return t('narratives.dropper_behavior', { proc, path: conn.exe })
        }

        // 0. COMPOSITE: Anonymous Malware (Unsigned + Tor)
        if (isUnsigned && isTor) {
            return t('narratives.unsigned_tor', { proc })
        }

        // 1. CRITICAL: DNS Risk (Highest Priority)
        if (dnsRisk && dnsRisk.score > 50) {
            return t('narratives.malicious_domain', {
                proc,
                domain: conn.domain,
                reasons: dnsRisk.reasons.join(', ')
            })
        }

        // 2. CRITICAL: Minería
        if (isMining) {
            const signature = isUnsigned ? t('narratives.no_signature') : t('narratives.third_party')
            const resources = isHighRes ? t('narratives.consuming_resources') : t('narratives.maintains_connection')
            return t('narratives.crypto_mining', { proc, signature, resources })
        }

        // 3. CRITICAL: Tor / Anonimato
        if (isTor) {
            return t('narratives.tor_traffic', { proc })
        }

        // 4. CRITICAL: Beacon + Unsigned
        if (isBeacon && isUnsigned) {
            return t('narratives.beacon_behavior', { proc })
        }

        // 5. WARNING: DNS Suspicious
        if (dnsRisk && dnsRisk.score > 20) {
            return t('narratives.suspicious_domain', {
                proc,
                domain: conn.domain,
                reasons: dnsRisk.reasons.join(', ')
            })
        }

        // 6. WARNING: Ejecución desde /tmp
        if (isTmp) {
            return t('narratives.tmp_execution', { proc })
        }

        // 7. WARNING: Alto Consumo
        if (isHighRes) {
            const context = isApple ? t('narratives.apple_context') : t('narratives.third_party_context')
            return t('narratives.high_resources', { proc, context })
        }

        // 8. WARNING: Sin firma + Internet
        if (isUnsigned && isPublic) {
            return t('narratives.unsigned_internet', { proc })
        }

        // 9. INFO: Apple / Sistema (Solo si no hay riesgos anteriores)
        if (isApple) {
            return t('narratives.system_process', { proc })
        }

        // 10. INFO: Firmado Genérico
        if (conn.signed) {
            return t('narratives.verified_app', { proc, type: getIpType(hostFrom(conn.raddr)) })
        }

        // Fallback genérico
        return t('narratives.generic', { proc, pid: conn.pid })
    }

    // Generar motivos legibles
    const getReasons = (conn) => {
        const reasons = conn.reasons || []
        const map = {
            'Puerto sensible': t('evidence.sensitive_port'),
            'Ejecutable en carpeta temporal': t('evidence.temp_folder'),
            'Conecta a Internet (IP pública)': t('evidence.internet_connection'),
            'Patrón repetitivo de conexión': t('evidence.repeated_connections'),
            'Muchos destinos distintos': t('evidence.many_destinations'),
            'Aplicación sin firma': t('evidence.unsigned_app'),
            'Aplicación de Apple': t('evidence.apple_app'),
            'Marcado como descargado recientemente': t('evidence.downloaded_recently'),
            'Ejecutable en carpeta de usuario': t('evidence.user_folder'),
        }

        return reasons.slice(0, 3).map(r => map[r] || r.toLowerCase()).join(', ') || t('evidence.network_activity')
    }

    const canKill = connection.level === 'alto' || connection.level === 'medio'

    const handleKill = async () => {
        setConfirmDialog({
            title: '¿Terminar Proceso?',
            message: `PID: ${connection.pid}\nProceso: ${connection.proc}\n\nEsta acción enviará SIGKILL (terminación forzada).\n\n⚠️ Esta acción es IRREVERSIBLE.`,
            danger: true,
            confirmText: 'Terminar Ahora',
            onConfirm: async () => {
                setLoading(true)
                try {
                    const res = await fetch(`/api/proc_kill?pid=${connection.pid}`, { method: 'POST' })
                    const data = await res.json()

                    if (data && data.ok) {
                        setConfirmDialog({
                            title: 'Proceso Terminado',
                            message: `El proceso ${connection.pid} fue terminado exitosamente.`,
                            type: 'success'
                        })
                        setTimeout(() => {
                            onClose()
                            window.location.reload()
                        }, 1500)
                    } else {
                        setConfirmDialog({
                            title: 'Error',
                            message: data.error || 'No se pudo terminar el proceso',
                            type: 'alert'
                        })
                    }
                } catch (err) {
                    setConfirmDialog({
                        title: 'Error',
                        message: `Error al terminar proceso: ${err.message}`,
                        type: 'alert'
                    })
                } finally {
                    setLoading(false)
                }
            }
        })
    }

    const handleKillTree = async () => {
        const count = processInfo?.children_count || 0
        setConfirmDialog({
            title: '¿Terminar Árbol de Procesos?',
            message: `PID: ${connection.pid}\nDescendientes: ${count}\n\nEsto terminará el proceso y TODOS sus hijos recursivamente.\n\n⚠️ Esta acción es IRREVERSIBLE.`,
            danger: true,
            confirmText: 'Terminar Árbol',
            onConfirm: async () => {
                setLoading(true)
                try {
                    const res = await fetch(`/api/proc_kill_tree?pid=${connection.pid}`, { method: 'POST' })
                    const data = await res.json()

                    if (data && data.ok) {
                        setConfirmDialog({
                            title: 'Árbol Terminado',
                            message: `Se terminaron ${(data.killed || []).length} procesos.`,
                            type: 'success'
                        })
                        setTimeout(() => {
                            onClose()
                            window.location.reload()
                        }, 1500)
                    } else {
                        setConfirmDialog({
                            title: 'Error',
                            message: data.error || 'No se pudo terminar el árbol',
                            type: 'alert'
                        })
                    }
                } catch (err) {
                    setConfirmDialog({
                        title: 'Error',
                        message: `Error al terminar árbol: ${err.message}`,
                        type: 'alert'
                    })
                } finally {
                    setLoading(false)
                }
            }
        })
    }

    const handleKillPGID = async () => {
        const pgid = processInfo?.pgid
        setConfirmDialog({
            title: '¿Terminar Grupo de Procesos?',
            message: `PID: ${connection.pid}\nPGID: ${pgid}\n\nEsto terminará TODO el grupo de procesos (útil para scripts que relanzan hijos).\n\n⚠️ Esta acción es IRREVERSIBLE.`,
            danger: true,
            confirmText: 'Terminar Grupo',
            onConfirm: async () => {
                setLoading(true)
                try {
                    const res = await fetch(`/api/proc_kill_pgid?pid=${connection.pid}`, { method: 'POST' })
                    const data = await res.json()

                    if (data && data.ok) {
                        setConfirmDialog({
                            title: 'Grupo Terminado',
                            message: `El grupo ${data.pgid} fue terminado exitosamente.`,
                            type: 'success'
                        })
                        setTimeout(() => {
                            onClose()
                            window.location.reload()
                        }, 1500)
                    } else {
                        setConfirmDialog({
                            title: 'Error',
                            message: data.error || 'No se pudo terminar el grupo',
                            type: 'alert'
                        })
                    }
                } catch (err) {
                    setConfirmDialog({
                        title: 'Error',
                        message: `Error al terminar grupo: ${err.message}`,
                        type: 'alert'
                    })
                } finally {
                    setLoading(false)
                }
            }
        })
    }

    const handleBootout = async () => {
        const label = processInfo?.launchd?.label
        setConfirmDialog({
            title: '¿Hacer Bootout del Servicio?',
            message: `Label: ${label}\n\nEsto intentará desinstalar/deshabilitar el servicio launchd.\n\nEl proceso no se relanzará al reiniciar.`,
            danger: true,
            confirmText: 'Ejecutar Bootout',
            onConfirm: async () => {
                setLoading(true)
                try {
                    const res = await fetch(`/api/proc_bootout?pid=${connection.pid}`, { method: 'POST' })
                    const data = await res.json()

                    if (data && data.ok) {
                        const lines = (data.results || []).map(r => `${r.cmd} (rc=${r.rc})\n${(r.stdout || '').trim()}\n${(r.stderr || '').trim()}`).join('\n\n')
                        setConfirmDialog({
                            title: 'Bootout Ejecutado',
                            message: lines || 'Comando ejecutado correctamente',
                            type: 'success'
                        })
                        setTimeout(() => {
                            onClose()
                            window.location.reload()
                        }, 2000)
                    } else {
                        setConfirmDialog({
                            title: 'Error',
                            message: data.error || 'No se pudo ejecutar bootout',
                            type: 'alert'
                        })
                    }
                } catch (err) {
                    setConfirmDialog({
                        title: 'Error',
                        message: `Error al ejecutar bootout: ${err.message}`,
                        type: 'alert'
                    })
                } finally {
                    setLoading(false)
                }
            }
        })
    }

    const description = getNarrative(connection)
    const reasons = getReasons(connection)

    const levelColor = {
        alto: { bg: "bg-red-500/10", border: "border-red-500/30", text: "text-red-400" },
        medio: { bg: "bg-yellow-500/10", border: "border-yellow-500/30", text: "text-yellow-400" },
        bajo: { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-400" }
    }[connection.level] || { bg: "bg-slate-500/10", border: "border-slate-500/30", text: "text-slate-400" }

    // Use Portal to render outside of table stacking context
    return createPortal(
        <>
            <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
                <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200" onClick={e => e.stopPropagation()}>

                    {/* Header */}
                    <div className="p-6 border-b border-slate-800/50 bg-slate-900/50 flex items-start justify-between">
                        <div className="flex items-start gap-4">
                            <div className={cn(
                                "p-3 rounded-xl border shadow-lg",
                                levelColor.bg, levelColor.border, levelColor.text
                            )}>
                                <ProcessIcon pid={connection.pid} className="w-8 h-8" />
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                    {connection.proc}
                                    <span className="text-sm font-normal text-slate-400 font-mono bg-slate-800/50 px-2 py-0.5 rounded flex items-center gap-1">
                                        PID: {connection.pid}
                                        <CopyButton text={connection.pid} className="opacity-50 hover:opacity-100" />
                                    </span>
                                </h2>
                                <div className="flex items-center gap-2 text-sm text-slate-400 mt-1">
                                    <span className="font-mono max-w-[300px] truncate" title={connection.exe}>
                                        {connection.exe}
                                    </span>
                                    <CopyButton text={connection.exe} className="opacity-50 hover:opacity-100" />
                                </div>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Scrollable Body */}
                    <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">

                        {/* Análisis en Lenguaje Natural */}
                        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
                            <h4 className="text-sm font-medium text-slate-300 mb-2 flex items-center gap-2">
                                <Info className="w-4 h-4 text-blue-400" />
                                {t('detailsModal.whats_happening')}
                            </h4>
                            <p className="text-sm text-slate-300 leading-relaxed">
                                {description}
                            </p>
                        </div>

                        {/* Motivos / Evidencia */}
                        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
                            <h4 className="text-sm font-medium text-slate-300 mb-2 flex items-center gap-2">
                                <FileText className="w-4 h-4 text-amber-400" />
                                {t('detailsModal.evidence_detected')}
                            </h4>
                            <p className="text-sm text-slate-400">
                                {reasons}
                            </p>
                        </div>

                        {/* Información Técnica */}
                        <div>
                            <h4 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
                                <Server className="w-4 h-4 text-slate-500" />
                                {t('detailsModal.technical_details')}
                            </h4>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3 text-sm">

                                <div className="space-y-1">
                                    <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.user')}</label>
                                    <div className="flex items-center gap-2 text-slate-300">
                                        <User className="w-3 h-3 text-slate-500" />
                                        {connection.user || 'N/A'}
                                    </div>
                                </div>

                                <div className="space-y-1">
                                    <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.status')}</label>
                                    <div className="flex items-center gap-2 text-slate-300">
                                        <div className={cn("w-2 h-2 rounded-full",
                                            connection.status === "ESTABLISHED" ? "bg-emerald-500" : "bg-slate-500"
                                        )} />
                                        {connection.status}
                                    </div>
                                </div>

                                <div className="space-y-1">
                                    <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.local_address')}</label>
                                    <div className="text-slate-300 font-mono text-xs">
                                        {connection.laddr || 'N/A'}
                                    </div>
                                </div>

                                <div className="space-y-1">
                                    <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.remote_address')}</label>
                                    <div className="flex items-center gap-2 text-slate-300 font-mono text-xs">
                                        <Globe className="w-3 h-3 text-slate-500" />
                                        {connection.raddr || 'N/A'}
                                    </div>
                                </div>

                                {/* Domain (if resolved) */}
                                {connection.domain && (
                                    <div className="space-y-1">
                                        <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.domain')}</label>
                                        <div className="flex items-center gap-2 text-slate-300 text-xs">
                                            <span className={cn(
                                                "px-2 py-1 rounded font-medium",
                                                connection.dns_risk?.score > 50 ? "bg-red-900/30 text-red-400 border border-red-900/50" :
                                                    connection.dns_risk?.score > 20 ? "bg-amber-900/30 text-amber-400 border border-amber-900/50" :
                                                        "bg-slate-800 text-slate-400 border border-slate-700"
                                            )}>
                                                {connection.domain}
                                            </span>
                                        </div>
                                    </div>
                                )}

                                {/* DNS Risk Score (if available) */}
                                {connection.dns_risk?.score !== undefined && (
                                    <div className="space-y-1">
                                        <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.dns_risk')}</label>
                                        <div className="flex items-center gap-2 text-xs">
                                            <span className={cn(
                                                "px-2 py-1 rounded font-medium",
                                                connection.dns_risk.score > 50 ? "bg-red-900/30 text-red-400 border border-red-900/50" :
                                                    connection.dns_risk.score > 20 ? "bg-amber-900/30 text-amber-400 border border-amber-900/50" :
                                                        "bg-emerald-900/30 text-emerald-400 border border-emerald-900/50"
                                            )}>
                                                {connection.dns_risk.score.toFixed(0)}% - {connection.dns_risk.risk}
                                            </span>
                                            {connection.dns_risk.reasons && connection.dns_risk.reasons.length > 0 && (
                                                <span className="text-slate-500 text-xs">
                                                    ({connection.dns_risk.reasons.join(', ')})
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                )}

                                <div className="space-y-1">
                                    <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.port_service')}</label>
                                    <div className="text-slate-300 text-xs">
                                        {connection.dport || 'N/A'} {connection.service && `(${connection.service})`}
                                    </div>
                                </div>

                                <div className="space-y-1">
                                    <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.location')}</label>
                                    <div className="text-slate-300 text-xs">
                                        {connection.country ? (
                                            <span>{connection.country} {connection.country_name}</span>
                                        ) : (
                                            <span className="text-slate-600">Local / Desconocido</span>
                                        )}
                                    </div>
                                </div>

                                <div className="space-y-1">
                                    <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.unique_destinations')}</label>
                                    <div className="flex items-center gap-2 text-slate-300 text-xs">
                                        <Network className="w-3 h-3 text-slate-500" />
                                        {connection.unique_dsts || 1}
                                    </div>
                                </div>

                                <div className="space-y-1">
                                    <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.risk_level')}</label>
                                    <div className="flex items-center gap-2">
                                        {connection.score > 5 ? (
                                            <AlertTriangle className="w-3 h-3 text-red-500" />
                                        ) : (
                                            <Shield className="w-3 h-3 text-emerald-500" />
                                        )}
                                        <span className={cn(
                                            "text-xs font-mono",
                                            connection.score > 7 ? "text-red-400" :
                                                connection.score > 4 ? "text-amber-400" : "text-emerald-400"
                                        )}>
                                            {connection.score?.toFixed(1) || '0.0'} / 10
                                        </span>
                                    </div>
                                </div>

                                <div className="col-span-full space-y-1">
                                    <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.executable')}</label>
                                    <div className="text-slate-300 font-mono text-xs break-all">
                                        {connection.exe || 'N/A'}
                                    </div>
                                </div>

                                <div className="col-span-full space-y-1">
                                    <label className="text-xs text-slate-500 uppercase font-bold tracking-wider">{t('detailsModal.signature_origin')}</label>
                                    <div className="text-slate-300 text-xs">
                                        {connection.apple ? 'Aplicación de Apple' :
                                            connection.signed ? 'Firmada por terceros' : '⚠ Sin firma digital'}
                                        {connection.quarantine && ' • ⚠ Descargada recientemente'}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Process Control Actions (only for suspicious connections) */}
                        {canKill && (
                            <div className="bg-red-950/20 border border-red-900/50 rounded-lg p-4">
                                <h4 className="text-sm font-medium text-red-300 mb-3 flex items-center gap-2">
                                    <AlertTriangle className="w-4 h-4" />
                                    Acciones de control (Modo avanzado)
                                </h4>
                                <p className="text-xs text-red-200/70 mb-3">
                                    Estas acciones son irreversibles. Úsalas solo si estás seguro de que este proceso es malicioso.
                                </p>
                                <div className="flex flex-wrap gap-2">
                                    <button
                                        onClick={handleKill}
                                        disabled={loading}
                                        className="px-3 py-2 bg-red-700 hover:bg-red-600 disabled:bg-red-900/50 text-white rounded-lg text-xs font-medium transition-colors flex items-center gap-2 border border-red-900"
                                    >
                                        <Skull className="w-3 h-3" />
                                        KILL (SIGKILL)
                                    </button>

                                    {processInfo && processInfo.children_count > 0 && (
                                        <button
                                            onClick={handleKillTree}
                                            disabled={loading}
                                            className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-900/50 text-white rounded-lg text-xs font-medium transition-colors flex items-center gap-2 border border-slate-800"
                                        >
                                            <Zap className="w-3 h-3" />
                                            Kill árbol ({processInfo.children_count})
                                        </button>
                                    )}

                                    {processInfo && processInfo.pgid && (
                                        <button
                                            onClick={handleKillPGID}
                                            disabled={loading}
                                            className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-900/50 text-white rounded-lg text-xs font-medium transition-colors flex items-center gap-2 border border-slate-800"
                                        >
                                            <Users className="w-3 h-3" />
                                            Kill grupo (pgid {processInfo.pgid})
                                        </button>
                                    )}

                                    {processInfo && processInfo.launchd && processInfo.launchd.label && (
                                        <button
                                            onClick={handleBootout}
                                            disabled={loading}
                                            className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-900/50 text-white rounded-lg text-xs font-medium transition-colors border border-slate-800"
                                        >
                                            Bootout {processInfo.launchd.label}
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Footer */}
                    <div className="p-4 border-t border-slate-800 bg-slate-900/50 flex justify-between items-center">
                        <div className="text-xs text-slate-500">
                            {loading && 'Ejecutando acción...'}
                        </div>
                        <button
                            onClick={onClose}
                            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-colors"
                        >
                            {t('detailsModal.close')}
                        </button>
                    </div>

                </div>
            </div>

            {/* Custom Confirm/Alert Modal */}
            {confirmDialog && (
                <ConfirmModal
                    isOpen={true}
                    onClose={() => setConfirmDialog(null)}
                    onConfirm={confirmDialog.onConfirm}
                    title={confirmDialog.title}
                    message={confirmDialog.message}
                    type={confirmDialog.type || 'confirm'}
                    danger={confirmDialog.danger}
                    confirmText={confirmDialog.confirmText}
                    cancelText={confirmDialog.cancelText}
                />
            )}
        </>,
        document.body
    )
}

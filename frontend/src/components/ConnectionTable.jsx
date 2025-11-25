import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MoreHorizontal, ChevronDown, ChevronRight, Network, Skull, PauseCircle, ShieldAlert, Info, Globe } from 'lucide-react'
import { Chips } from './Chips'
import { cn } from '../lib/utils'
import { ConnectionDetailsModal } from './ConnectionDetailsModal'
import { CopyButton } from './CopyButton'
import { ProcessIcon } from './ProcessIcon'
import { useTranslation } from 'react-i18next'

function getFlagEmoji(countryCode) {
    if (!countryCode) return ''
    const codePoints = countryCode
        .toUpperCase()
        .split('')
        .map(char => 127397 + char.charCodeAt(0));
    return String.fromCodePoint(...codePoints);
}

export function ConnectionTable({ rows, paranoidMode }) {
    const { t } = useTranslation()
    const [selectedConnection, setSelectedConnection] = useState(null)

    // Group rows by PID
    const groupedRows = useMemo(() => {
        const groups = {}
        rows.forEach(row => {
            if (!groups[row.pid]) {
                groups[row.pid] = {
                    ...row,
                    connections: []
                }
            }
            groups[row.pid].connections.push(row)
        })
        return Object.values(groups).sort((a, b) => b.score - a.score)
    }, [rows])

    const handleAction = async (action, pid, e) => {
        e.stopPropagation()
        if (!confirm(t('table.confirm_action', { action: action.toUpperCase(), pid }))) return

        try {
            const endpoint = action === 'kill' ? '/api/proc_kill' : '/api/proc_stop'
            await fetch(`${endpoint}?pid=${pid}`, { method: 'POST' })
        } catch (err) {
            console.error('Error executing action', err)
        }
    }

    return (
        <>
            <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                    <thead className="text-xs text-slate-400 uppercase bg-slate-900/50 border-b border-slate-800">
                        <tr>
                            <th className="px-4 py-3 w-8"></th>
                            <th className="px-4 py-3">{t('table.score')}</th>
                            <th className="px-4 py-3">{t('table.level')}</th>
                            <th className="px-4 py-3">{t('table.proc')}</th>
                            <th className="px-4 py-3">{t('table.pid')}</th>
                            <th className="px-4 py-3">{t('table.user')}</th>
                            <th className="px-4 py-3">{t('table.connections')}</th>
                            <th className="px-4 py-3">{t('table.evidence')}</th>
                            <th className="px-4 py-3 text-right">{t('table.actions')}</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                        <AnimatePresence initial={false}>
                            {groupedRows.map((group) => (
                                <RowGroup
                                    key={group.pid}
                                    group={group}
                                    paranoidMode={paranoidMode}
                                    onAction={handleAction}
                                    onSelect={setSelectedConnection}
                                    t={t}
                                />
                            ))}
                        </AnimatePresence>
                    </tbody>
                </table>
            </div>

            <ConnectionDetailsModal
                connection={selectedConnection}
                onClose={() => setSelectedConnection(null)}
            />
        </>
    )
}

function RowGroup({ group, paranoidMode, onAction, onSelect, t }) {
    const [isExpanded, setIsExpanded] = useState(false)
    const hasMultiple = group.connections.length > 1

    const handleClick = () => {
        if (hasMultiple) {
            setIsExpanded(!isExpanded)
        } else {
            onSelect(group)
        }
    }

    return (
        <>
            <motion.tr
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className={cn(
                    "hover:bg-slate-800/30 transition-colors cursor-pointer group",
                    group.level === 'alto' && "bg-red-950/10 hover:bg-red-900/20",
                    group.level === 'medio' && "bg-yellow-950/10 hover:bg-yellow-900/20"
                )}
                onClick={handleClick}
            >
                <td className="px-4 py-3 text-slate-500">
                    {hasMultiple && (
                        isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />
                    )}
                </td>
                <td className="px-4 py-3 font-mono text-slate-300">
                    <div className={cn(
                        "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border",
                        group.score >= 7 ? "border-red-500/30 bg-red-500/10 text-red-400" :
                            group.score >= 4 ? "border-yellow-500/30 bg-yellow-500/10 text-yellow-400" :
                                "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                    )}>
                        {group.score.toFixed(0)}
                    </div>
                </td>
                <td className="px-4 py-3">
                    <span className={cn(
                        "px-2 py-1 rounded text-[10px] uppercase font-bold tracking-wider",
                        group.level === 'alto' ? "bg-red-500 text-white shadow-sm shadow-red-500/20" :
                            group.level === 'medio' ? "bg-yellow-500 text-black shadow-sm shadow-yellow-500/20" :
                                "bg-emerald-500/20 text-emerald-400"
                    )}>
                        {group.level}
                    </span>
                </td>
                <td className="px-4 py-3 font-medium text-slate-200">
                    <div className="flex flex-col">
                        <div className="flex items-center gap-2">
                            <ProcessIcon pid={group.pid} className="w-4 h-4" />
                            <span className="group-hover:text-blue-400 transition-colors">{group.proc}</span>
                            <CopyButton text={group.proc} className="opacity-0 group-hover:opacity-100" />
                        </div>
                        <span className="text-[10px] text-slate-500 font-mono truncate max-w-[150px]" title={group.exe}>{group.exe}</span>
                    </div>
                </td>
                <td className="px-4 py-3 font-mono text-slate-500 text-xs">
                    <div className="flex items-center gap-1">
                        {group.pid}
                        <CopyButton text={group.pid} className="opacity-0 group-hover:opacity-100" />
                    </div>
                </td>
                <td className="px-4 py-3 text-slate-400">{group.user}</td>
                <td className="px-4 py-3">
                    <div className="flex items-center gap-2 text-slate-400 text-xs">
                        <Network className="w-4 h-4" />
                        {group.connections.length} {hasMultiple ? t('table.connections_plural') : t('table.connection_singular')}
                    </div>
                </td>
                <td className="px-4 py-3 max-w-[200px]">
                    <div className="flex flex-wrap gap-1">
                        <Chips row={group} />
                        {/* Alert Badge */}
                        {group.alert_info && (
                            <>
                                {group.alert_info.status === 'pending' && (
                                    <span className="px-2 py-0.5 text-[10px] rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center gap-1 animate-pulse">
                                        🔔 ALERTA
                                    </span>
                                )}
                                {group.alert_info.status === 'resolved' && group.alert_info.decision === 'allow' && (
                                    <span className="px-2 py-0.5 text-[10px] rounded-full bg-green-500/20 text-green-400 border border-green-500/30 flex items-center gap-1">
                                        ✅ PERMITIDO
                                    </span>
                                )}
                                {group.alert_info.status === 'resolved' && group.alert_info.decision === 'deny' && (
                                    <span className="px-2 py-0.5 text-[10px] rounded-full bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-1">
                                        🚫 BLOQUEADO
                                    </span>
                                )}
                            </>
                        )}
                    </div>
                </td>
                <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                        {paranoidMode && (
                            <>
                                <button
                                    onClick={(e) => onAction('stop', group.pid, e)}
                                    className="p-1.5 bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 rounded border border-yellow-500/30"
                                    title="Terminar proceso (SIGTERM)"
                                >
                                    <PauseCircle className="w-4 h-4" />
                                </button>
                                <button
                                    onClick={(e) => onAction('kill', group.pid, e)}
                                    className="p-1.5 bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded border border-red-500/30"
                                    title="Matar proceso (SIGKILL)"
                                >
                                    <Skull className="w-4 h-4" />
                                </button>
                            </>
                        )}
                        <button
                            onClick={(e) => { e.stopPropagation(); onSelect(group); }}
                            className="p-2 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors"
                            title="Ver detalles"
                        >
                            <Info className="w-4 h-4" />
                        </button>
                    </div>
                </td>
            </motion.tr>

            <AnimatePresence>
                {isExpanded && hasMultiple && (
                    <motion.tr
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                    >
                        <td colSpan={9} className="p-0 bg-slate-900/30 border-b border-slate-800/50">
                            <div className="px-4 py-2 pl-12 space-y-1">
                                {group.connections.map((conn, idx) => (
                                    <div
                                        key={idx}
                                        className="group/sub flex items-center gap-4 text-sm py-2 px-4 hover:bg-slate-800/50 rounded-lg transition-colors cursor-pointer"
                                        onClick={() => onSelect(conn)}
                                    >
                                        {/* IP / Domain */}
                                        <div className="flex-none w-48">
                                            <div className="flex items-center gap-2 text-slate-300 font-mono text-sm">
                                                <Globe className="w-3 h-3 text-slate-500" />
                                                {conn.raddr}
                                                <CopyButton text={conn.raddr} className="opacity-0 group-hover/sub:opacity-50 hover:!opacity-100" />
                                            </div>
                                            {conn.domain && (
                                                <div className="flex items-center gap-1.5 mt-0.5">
                                                    <span className={cn(
                                                        "text-xs px-1.5 py-0.5 rounded font-medium truncate max-w-[180px]",
                                                        conn.dns_risk?.score > 50 ? "bg-red-900/30 text-red-400 border border-red-900/50" :
                                                            conn.dns_risk?.score > 20 ? "bg-amber-900/30 text-amber-400 border border-amber-900/50" :
                                                                "bg-slate-800 text-slate-400 border border-slate-700"
                                                    )} title={conn.domain}>
                                                        {conn.domain}
                                                    </span>
                                                </div>
                                            )}
                                        </div>

                                        {/* Country Flag */}
                                        <div className="flex-none w-8">
                                            {conn.country && (
                                                <span title={conn.country_name} className="text-base cursor-help">
                                                    {getFlagEmoji(conn.country)}
                                                </span>
                                            )}
                                        </div>

                                        {/* DNS Risk Badge */}
                                        <div className="flex-none w-16">
                                            {conn.dns_risk?.score !== undefined && (
                                                <span
                                                    className={cn(
                                                        "text-xs px-1.5 py-0.5 rounded font-medium cursor-help",
                                                        conn.dns_risk.score > 50 ? "bg-red-900/30 text-red-400 border border-red-900/50" :
                                                            conn.dns_risk.score > 20 ? "bg-amber-900/30 text-amber-400 border border-amber-900/50" :
                                                                "bg-emerald-900/30 text-emerald-400 border border-emerald-900/50"
                                                    )}
                                                    title={`Riesgo DNS: ${conn.dns_risk.score.toFixed(0)}%\n${conn.dns_risk.reasons.join('\n')}`}
                                                >
                                                    {conn.dns_risk.score.toFixed(0)}%
                                                </span>
                                            )}
                                        </div>

                                        {/* Port & Service */}
                                        <div className="flex-none w-32 text-slate-400 font-mono text-xs">
                                            {conn.dport} {conn.service}
                                        </div>

                                        {/* Status */}
                                        <div className="flex-none w-24 text-slate-500 text-xs">
                                            {conn.status}
                                        </div>

                                        {/* Details Link */}
                                        <div className="flex-1 flex justify-end">
                                            <span className="text-blue-400 opacity-0 group-hover/sub:opacity-100 transition-opacity flex items-center gap-1 text-xs">
                                                <Info className="w-3 h-3" /> {t('table.details')}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </td>
                    </motion.tr>
                )}
            </AnimatePresence>
        </>
    )
}

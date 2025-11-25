import { X, ShieldOff, Trash2, Info, Clock, Globe } from 'lucide-react'
import { cn } from '../lib/utils'
import { useState } from 'react'
import { ConfirmModal } from './ConfirmModal'
import { ConnectionDetailsModal } from './ConnectionDetailsModal'
import { useTranslation, Trans } from 'react-i18next'

export function BlockedProcessesPanel({ rules, onClose, onUnblock }) {
    const { t } = useTranslation()
    const [selectedRule, setSelectedRule] = useState(null)
    const [confirmUnblock, setConfirmUnblock] = useState(null)
    const [selectedConnection, setSelectedConnection] = useState(null)

    // Filter only deny rules
    const deniedRules = rules.filter(rule => rule.action === 'deny' && rule.enabled)

    if (deniedRules.length === 0) {
        return null
    }

    const formatDate = (isoString) => {
        if (!isoString) return 'N/A'
        return new Date(isoString).toLocaleString('es-ES', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        })
    }

    const formatScope = (scope) => {
        const scopes = {
            'once': t('blockedProcesses.scope_once'),
            'temporary': t('blockedProcesses.scope_temporary'),
            'always': t('blockedProcesses.scope_always')
        }
        return scopes[scope] || scope
    }

    const getScopeColor = (scope) => {
        const colors = {
            'once': 'text-blue-400 bg-blue-500/10 border-blue-500/30',
            'temporary': 'text-amber-400 bg-amber-500/10 border-amber-500/30',
            'always': 'text-red-400 bg-red-500/10 border-red-500/30'
        }
        return colors[scope] || 'text-slate-400 bg-slate-500/10 border-slate-500/30'
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <div className="w-full max-w-3xl bg-slate-900 border border-red-900/30 rounded-xl shadow-2xl overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-red-900/30 bg-red-950/20">
                    <div className="flex items-center gap-2">
                        <ShieldOff className="w-5 h-5 text-red-400" />
                        <h2 className="text-lg font-semibold text-white">
                            {t('blockedProcesses.title')} ({deniedRules.length})
                        </h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1 hover:bg-slate-800 rounded-lg transition-colors"
                    >
                        <X className="w-5 h-5 text-slate-400" />
                    </button>
                </div>

                {/* Info Banner */}
                <div className="px-6 py-3 bg-red-950/10 border-b border-red-900/20">
                    <p className="text-sm text-slate-300">
                        <Trans i18nKey="blockedProcesses.info_banner">
                            💀 Los procesos listados serán <strong>automáticamente matados</strong> cuando intenten ejecutarse.
                            Click en "Desbloquear" para permitirlos.
                        </Trans>
                    </p>
                </div>

                {/* Rules List */}
                <div className="max-h-[60vh] overflow-y-auto p-6 space-y-3">
                    {deniedRules.map((rule) => (
                        <div
                            key={rule.id}
                            className="bg-slate-950/50 border border-red-900/30 rounded-lg p-4 hover:border-red-800/50 transition-colors"
                        >
                            <div className="flex items-start justify-between gap-4">
                                {/* Process Info */}
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="font-medium text-white text-lg">
                                            {rule.process || 'Unknown Process'}
                                        </span>
                                        <span className={cn(
                                            "text-xs px-2 py-0.5 rounded-full border",
                                            getScopeColor(rule.scope)
                                        )}>
                                            {formatScope(rule.scope)}
                                        </span>
                                    </div>

                                    {/* Destination */}
                                    {rule.destination && (
                                        <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
                                            <Globe className="w-4 h-4" />
                                            <span className="font-mono">{rule.destination}</span>
                                            {rule.port && <span>:{rule.port}</span>}
                                        </div>
                                    )}

                                    {/* Created At */}
                                    <div className="flex items-center gap-2 text-xs text-slate-500">
                                        <Clock className="w-3 h-3" />
                                        {t('blockedProcesses.blocked_at')} {formatDate(rule.created_at)}
                                    </div>

                                    {/* Expiration for temporary */}
                                    {rule.scope === 'temporary' && rule.expires_at && (
                                        <div className="flex items-center gap-2 text-xs text-amber-400 mt-1">
                                            <Clock className="w-3 h-3" />
                                            {t('blockedProcesses.expires_at')} {formatDate(rule.expires_at)}
                                        </div>
                                    )}

                                    {/* User Comment */}
                                    {rule.user_comment && (
                                        <div className="mt-2 text-sm text-slate-300 italic">
                                            "{rule.user_comment}"
                                        </div>
                                    )}

                                    {/* Exe Path */}
                                    {rule.exe_path && (
                                        <div className="mt-2 text-xs text-slate-600 font-mono truncate" title={rule.exe_path}>
                                            {rule.exe_path}
                                        </div>
                                    )}
                                </div>

                                {/* Actions */}
                                <div className="flex flex-col gap-2">
                                    <button
                                        onClick={() => {
                                            // Construct connection object from rule context + rule info
                                            const context = rule.context || {}
                                            const conn = {
                                                ...context,
                                                pid: context.pid || 0, // Rules might not have PID if old
                                                proc: rule.process,
                                                exe: rule.exe_path || context.exe,
                                                raddr: `${rule.destination}:${rule.port || ''}`,
                                                dport: rule.port,
                                                level: context.level || 'medio',
                                                // Ensure we have enough data for the modal
                                                reasons: context.reasons || [],
                                                dns_risk: context.dns_risk,
                                                country: context.country,
                                                user: context.user
                                            }
                                            setSelectedConnection(conn)
                                        }}
                                        className="p-2 hover:bg-slate-800 rounded-lg transition-colors text-slate-400 hover:text-blue-400"
                                        title={t('blockedProcesses.view_details')}
                                    >
                                        <Info className="w-5 h-5" />
                                    </button>
                                    <button
                                        onClick={() => setConfirmUnblock(rule)}
                                        className="p-2 hover:bg-red-900/30 rounded-lg transition-colors text-red-400 hover:text-red-300"
                                        title={t('blockedProcesses.unblock_button')}
                                    >
                                        <Trash2 className="w-5 h-5" />
                                    </button>
                                </div>
                            </div>

                            {/* Expanded Details */}
                            {selectedRule?.id === rule.id && (
                                <div className="mt-4 pt-4 border-t border-slate-800 animate-in fade-in slide-in-from-top-2 duration-200">

                                    {/* Header Section */}
                                    <div className="flex items-start gap-4 mb-6">
                                        <div className="p-3 rounded-xl border border-red-500/30 bg-red-500/10 shadow-lg shadow-red-900/20">
                                            <ShieldOff className="w-8 h-8 text-red-400" />
                                        </div>
                                        <div>
                                            <h3 className="text-xl font-bold text-white flex items-center gap-2">
                                                {rule.process}
                                                <span className="text-xs font-normal text-red-400 border border-red-900/50 bg-red-950/30 px-2 py-0.5 rounded-full uppercase tracking-wider">
                                                    {t('blockedProcesses.block')}
                                                </span>
                                            </h3>
                                            <div className="flex items-center gap-2 text-sm text-slate-400 mt-1">
                                                <span className="font-mono bg-slate-900 px-1.5 py-0.5 rounded text-slate-300 break-all">
                                                    {rule.exe_path || t('blockedProcesses.path_unknown')}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Info Grid */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                                        {/* Column 1: Connection Info */}
                                        <div className="space-y-4">
                                            <h4 className="text-sm font-medium text-slate-300 border-b border-slate-800 pb-2 flex items-center gap-2">
                                                <Globe className="w-4 h-4 text-blue-400" />
                                                {t('blockedProcesses.connection_details')}
                                            </h4>

                                            <div className="grid grid-cols-[100px_1fr] gap-y-3 text-sm">
                                                <div className="text-slate-500">{t('blockedProcesses.destination')}</div>
                                                <div className="text-slate-300 font-mono">{rule.destination}</div>

                                                <div className="text-slate-500">{t('blockedProcesses.port')}</div>
                                                <div className="text-slate-300 font-mono">{rule.port || 'Any'} ({rule.protocol})</div>

                                                <div className="text-slate-500">{t('blockedProcesses.scope_once')}</div>
                                                <div className="text-slate-300">
                                                    <span className={cn(
                                                        "px-2 py-0.5 rounded text-xs border",
                                                        getScopeColor(rule.scope)
                                                    )}>
                                                        {formatScope(rule.scope)}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Column 2: Rule Metadata */}
                                        <div className="space-y-4">
                                            <h4 className="text-sm font-medium text-slate-300 border-b border-slate-800 pb-2 flex items-center gap-2">
                                                <Clock className="w-4 h-4 text-amber-400" />
                                                {t('blockedProcesses.rule_metadata')}
                                            </h4>

                                            <div className="grid grid-cols-[100px_1fr] gap-y-3 text-sm">
                                                <div className="text-slate-500">{t('blockedProcesses.blocked_at')}</div>
                                                <div className="text-slate-300">{formatDate(rule.created_at)}</div>

                                                {rule.expires_at && (
                                                    <>
                                                        <div className="text-slate-500">{t('blockedProcesses.expires_at')}</div>
                                                        <div className="text-amber-400">{formatDate(rule.expires_at)}</div>
                                                    </>
                                                )}

                                                <div className="text-slate-500">{t('blockedProcesses.id')}</div>
                                                <div className="text-slate-500 font-mono text-xs truncate" title={rule.id}>{rule.id}</div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* User Comment Section if exists */}
                                    {rule.user_comment && (
                                        <div className="mt-6 bg-slate-900/50 p-4 rounded-lg border border-slate-800">
                                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                                                {t('blockedProcesses.comment')}
                                            </h4>
                                            <p className="text-slate-300 italic">"{rule.user_comment}"</p>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>

                {/* Footer */}
                <div className="px-6 py-4 border-t border-red-900/30 bg-red-950/10 flex items-center justify-between">
                    <div className="text-sm text-slate-400">
                        {t('blockedProcesses.tip')}
                    </div>
                    <button
                        onClick={onClose}
                        className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm font-medium transition-colors"
                    >
                        {t('blockedProcesses.close')}
                    </button>
                </div>
            </div>

            <ConfirmModal
                isOpen={!!confirmUnblock}
                onClose={() => setConfirmUnblock(null)}
                onConfirm={() => onUnblock(confirmUnblock.id)}

                title={t('blockedProcesses.unblock_confirm_title')}
                message={t('blockedProcesses.unblock_confirm_message', { process: confirmUnblock?.process })}
                confirmText={t('blockedProcesses.unblock_button')}
                type="confirm"
            />

            {selectedConnection && (
                <ConnectionDetailsModal
                    connection={selectedConnection}
                    onClose={() => setSelectedConnection(null)}
                />
            )}
        </div>
    )
}

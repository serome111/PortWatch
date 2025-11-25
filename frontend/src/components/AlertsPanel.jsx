import React, { useState } from 'react'
import { X, Shield, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import { cn } from '../lib/utils'
import { ProcessIcon } from './ProcessIcon'
import { useTranslation } from 'react-i18next'

export function AlertsPanel({ alerts, onDecide, onClose }) {
    const { t } = useTranslation()
    const [selectedScopes, setSelectedScopes] = useState({})

    if (!alerts || alerts.length === 0) {
        return (
            <div className="fixed bottom-4 right-4 bg-slate-800/95 backdrop-blur-sm border border-slate-700 rounded-lg shadow-2xl p-6 w-96">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <Shield className="w-5 h-5 text-green-400" />
                        <h3 className="font-semibold text-white">{t('alerts.title')}</h3>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>
                <div className="text-center py-8 text-slate-400">
                    <CheckCircle className="w-12 h-12 mx-auto mb-3 text-green-400/50" />
                    <p>{t('alerts.no_pending')}</p>
                    <p className="text-sm mt-1">{t('alerts.all_allowed')}</p>
                </div>
            </div>
        )
    }

    const handleDecide = (alertId, action) => {
        const scope = selectedScopes[alertId] || 'always'
        onDecide(alertId, action, scope)

        // Clear scope selection
        setSelectedScopes(prev => {
            const next = { ...prev }
            delete next[alertId]
            return next
        })
    }

    const setScope = (alertId, scope) => {
        setSelectedScopes(prev => ({
            ...prev,
            [alertId]: scope
        }))
    }

    return (
        <div className="fixed bottom-4 right-4 bg-slate-800/95 backdrop-blur-sm border border-slate-700 rounded-lg shadow-2xl w-[480px] max-h-[80vh] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-slate-700">
                <div className="flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-amber-400 animate-pulse" />
                    <h3 className="font-semibold text-white">
                        {t('alerts.count', { count: alerts.length })}
                    </h3>
                </div>
                <button
                    onClick={onClose}
                    className="text-slate-400 hover:text-white transition-colors"
                >
                    <X className="w-5 h-5" />
                </button>
            </div>

            {/* Alerts List */}
            <div className="overflow-y-auto flex-1">
                {alerts.map((alert) => {
                    const conn = alert.connection
                    const proc = conn.proc || conn.name || 'Unknown'
                    const dest = (conn.raddr || '').split(':')[0]
                    const port = conn.dport
                    const level = conn.level || 'medio'
                    const scope = selectedScopes[alert.id] || 'always'

                    const levelColors = {
                        bajo: 'text-green-400 bg-green-400/10 border-green-400/20',
                        medio: 'text-amber-400 bg-amber-400/10 border-amber-400/20',
                        alto: 'text-red-400 bg-red-400/10 border-red-400/20'
                    }

                    const levelIcons = {
                        bajo: '🟢',
                        medio: '🟡',
                        alto: '🔴'
                    }

                    return (
                        <div
                            key={alert.id}
                            className="p-4 border-b border-slate-700 last:border-b-0 hover:bg-slate-700/30 transition-colors"
                        >
                            {/* Connection Info */}
                            <div className="flex items-start gap-3 mb-3">
                                <div className="w-10 h-10 flex-shrink-0">
                                    <ProcessIcon pid={conn.pid} name={proc} />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="font-medium text-white truncate">{proc}</span>
                                        <span
                                            className={cn(
                                                'text-xs px-2 py-0.5 rounded-full border',
                                                levelColors[level]
                                            )}
                                        >
                                            {levelIcons[level]} {t(`risk.${level}`).toUpperCase()}
                                        </span>
                                    </div>
                                    <div className="text-sm text-slate-300">
                                        <span className="text-slate-400">{t('alerts.trying_to_connect')}</span>
                                        {' '}
                                        <span className="font-mono text-amber-400">{dest}</span>
                                        {port && <span className="text-slate-400">:{port}</span>}
                                        {conn.country && (
                                            <span className="ml-2 text-xs text-slate-400">
                                                📍 {conn.country}
                                            </span>
                                        )}
                                    </div>
                                    <div className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                                        <Clock className="w-3 h-3" />
                                        {new Date(alert.created_at).toLocaleTimeString('es-ES')}
                                    </div>
                                </div>
                            </div>

                            {/* Scope Selector */}
                            <div className="mb-3 flex gap-2">
                                <button
                                    onClick={() => setScope(alert.id, 'once')}
                                    className={cn(
                                        'flex-1 text-xs py-1.5 px-3 rounded border transition-all',
                                        scope === 'once'
                                            ? 'bg-blue-500/20 border-blue-500 text-blue-300'
                                            : 'bg-slate-700/50 border-slate-600 text-slate-400 hover:border-slate-500'
                                    )}
                                >
                                    {t('alerts.scope_once')}
                                </button>
                                <button
                                    onClick={() => setScope(alert.id, 'temporary')}
                                    className={cn(
                                        'flex-1 text-xs py-1.5 px-3 rounded border transition-all',
                                        scope === 'temporary'
                                            ? 'bg-blue-500/20 border-blue-500 text-blue-300'
                                            : 'bg-slate-700/50 border-slate-600 text-slate-400 hover:border-slate-500'
                                    )}
                                >
                                    {t('alerts.scope_24h')}
                                </button>
                                <button
                                    onClick={() => setScope(alert.id, 'always')}
                                    className={cn(
                                        'flex-1 text-xs py-1.5 px-3 rounded border transition-all',
                                        scope === 'always'
                                            ? 'bg-blue-500/20 border-blue-500 text-blue-300'
                                            : 'bg-slate-700/50 border-slate-600 text-slate-400 hover:border-slate-500'
                                    )}
                                >
                                    {t('alerts.scope_always')}
                                </button>
                            </div>

                            {/* Action Buttons */}
                            <div className="flex gap-2">
                                <button
                                    onClick={() => handleDecide(alert.id, 'deny')}
                                    className="flex-1 bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 text-red-300 font-medium py-2 px-4 rounded transition-all hover:scale-105"
                                >
                                    {t('alerts.block')}
                                </button>
                                <button
                                    onClick={() => handleDecide(alert.id, 'allow')}
                                    className="flex-1 bg-green-500/20 hover:bg-green-500/30 border border-green-500/50 text-green-300 font-medium py-2 px-4 rounded transition-all hover:scale-105"
                                >
                                    {t('alerts.allow')}
                                </button>
                            </div>
                        </div>
                    )
                })}
            </div>

            {/* Footer */}
            <div className="p-3 border-t border-slate-700 bg-slate-800/50 text-xs text-slate-400 text-center">
                {t('alerts.rules_saved')}
            </div>
        </div>
    )
}

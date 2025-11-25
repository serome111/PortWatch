import { useState } from 'react'
import { Skull, X, Clock, Cpu, Network, AlertTriangle } from 'lucide-react'
import { cn } from '../lib/utils'
import { ConnectionDetailsModal } from './ConnectionDetailsModal'

export function KilledProcessesBar({ killedProcesses, onClear }) {
    const [selectedProcess, setSelectedProcess] = useState(null)

    if (!killedProcesses || killedProcesses.length === 0) return null

    // Filter out processes killed by deny rules (those go to BlockedProcessesPanel)
    const paranoidKills = killedProcesses.filter(p => p.type !== 'block')

    if (paranoidKills.length === 0) return null

    const formatTime = (timestamp) => {
        const now = Date.now() / 1000
        const diff = Math.floor(now - timestamp)

        if (diff < 60) return `${diff}s ago`
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
        return `${Math.floor(diff / 3600)}h ago`
    }

    const getIcon = (type) => {
        if (type === 'resource') return <Cpu className="w-4 h-4" />
        if (type === 'network') return <Network className="w-4 h-4" />
        return <AlertTriangle className="w-4 h-4" />
    }

    const getTypeLabel = (type) => {
        if (type === 'resource') return 'Resource'
        if (type === 'network') return 'Network'
        return 'Unknown'
    }

    return (
        <div className="bg-gradient-to-r from-red-950/50 to-orange-950/50 border border-red-900/50 rounded-xl p-4 mb-6">
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <div className="p-2 bg-red-500/10 rounded-lg border border-red-500/20">
                        <Skull className="w-5 h-5 text-red-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-red-300">
                            Paranoid Mode Kills
                        </h3>
                        <p className="text-xs text-red-400/70">
                            {paranoidKills.length} process{paranoidKills.length !== 1 ? 'es' : ''} terminated automatically
                        </p>
                    </div>
                </div>
                {paranoidKills.length > 0 && (
                    <button
                        onClick={onClear}
                        className="px-3 py-1.5 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-300 rounded-lg transition-colors flex items-center gap-1.5"
                    >
                        <X className="w-3 h-3" />
                        Clear All
                    </button>
                )}
            </div>

            <div className="space-y-2 max-h-64 overflow-y-auto">
                {paranoidKills.map((kill, idx) => (
                    <div
                        key={idx}
                        onClick={() => setSelectedProcess({
                            ...kill,
                            // Adapter for ConnectionDetailsModal
                            reasons: kill.reason ? kill.reason.split(', ') : [],
                            status: 'KILLED',
                            score: kill.score || (kill.level === 'alto' ? 8 : 5)
                        })}
                        className={cn(
                            "flex items-center gap-3 p-3 rounded-lg border cursor-pointer",
                            "bg-slate-900/50 border-red-900/30 hover:border-red-800/50 hover:bg-red-900/10 transition-all"
                        )}
                    >
                        <div className="p-2 bg-red-500/10 rounded-lg border border-red-500/20">
                            {getIcon(kill.type)}
                        </div>

                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                                <span className="font-mono text-sm text-white font-medium truncate">
                                    {kill.proc}
                                </span>
                                <span className="text-xs text-slate-500">
                                    PID {kill.pid}
                                </span>
                                <span className={cn(
                                    "text-xs px-2 py-0.5 rounded-full",
                                    kill.type === 'resource'
                                        ? "bg-orange-500/10 text-orange-400 border border-orange-500/20"
                                        : "bg-red-500/10 text-red-400 border border-red-500/20"
                                )}>
                                    {getTypeLabel(kill.type)}
                                </span>
                                {kill.level && (
                                    <span className={cn(
                                        "text-xs px-2 py-0.5 rounded-full uppercase font-semibold",
                                        kill.level === 'alto'
                                            ? "bg-red-500/20 text-red-300 border border-red-500/30"
                                            : "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30"
                                    )}>
                                        {kill.level}
                                    </span>
                                )}
                            </div>

                            <div className="text-xs text-slate-400 truncate mb-1">
                                {kill.reason}
                            </div>

                            {kill.raddr && (
                                <div className="text-xs text-slate-500 font-mono">
                                    → {kill.raddr}{kill.dport ? `:${kill.dport}` : ''}
                                </div>
                            )}
                        </div>

                        <div className="flex items-center gap-1.5 text-xs text-slate-500">
                            <Clock className="w-3 h-3" />
                            {formatTime(kill.timestamp)}
                        </div>
                    </div>
                ))}
            </div>


            {
                selectedProcess && (
                    <ConnectionDetailsModal
                        connection={selectedProcess}
                        onClose={() => setSelectedProcess(null)}
                    />
                )
            }
        </div>
    )
}

import { useMemo } from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { Shield, Activity, Settings, Globe } from 'lucide-react'
import { cn } from '../lib/utils'
import { WorldMap } from './WorldMap'
import { GeoIPManager } from './GeoIPManager'
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'

export function Dashboard({ rows, onCountrySelect, selectedCountry, data, onCountryClick }) {
    const { t } = useTranslation()

    // Calculate stats
    const { stats, topProcesses, chartData } = useMemo(() => {
        const total = rows.length
        const highRisk = rows.filter(r => r.level === 'alto').length
        const mediumRisk = rows.filter(r => r.level === 'medio').length
        const lowRisk = rows.filter(r => r.level === 'bajo').length

        // Top processes
        const procsMap = {}
        rows.forEach(r => {
            const name = r.proc || 'Unknown'
            procsMap[name] = (procsMap[name] || 0) + 1
        })
        const topProcs = Object.entries(procsMap)
            .map(([name, count]) => {
                // Find a PID for this proc to show
                const pid = rows.find(r => r.proc === name)?.pid || '?'
                return { name, count, pid }
            })
            .sort((a, b) => b.count - a.count)
            .slice(0, 5) // Limit to top 5

        const uniqueProcs = Object.keys(procsMap).length

        return {
            stats: { total, highRisk, mediumRisk, lowRisk, uniqueProcs },
            topProcesses: topProcs
        }
    }, [rows])

    // GeoIP Status
    const [geoIPStatus, setGeoIPStatus] = useState({ exists: false })

    const checkGeoIP = () => {
        fetch('/api/geoip/status')
            .then(res => res.json())
            .then(setGeoIPStatus)
            .catch(console.error)
    }

    useEffect(() => {
        checkGeoIP()
        window.addEventListener('geoip-status-changed', checkGeoIP)
        return () => window.removeEventListener('geoip-status-changed', checkGeoIP)
    }, [])

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            {/* Risk Distribution */}
            <div className="bg-slate-900/50 p-6 rounded-xl border border-slate-800">
                <h3 className="text-sm font-medium text-slate-400 mb-4 flex items-center gap-2">
                    <Shield className="w-4 h-4" />
                    {t('dashboard.risk_distribution')}
                </h3>
                <div className="h-[200px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={[
                                    { name: t('risk.high'), value: stats.highRisk, color: '#ef4444' },
                                    { name: t('risk.medium'), value: stats.mediumRisk, color: '#eab308' },
                                    { name: t('risk.low'), value: stats.lowRisk, color: '#10b981' },
                                ]}
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={80}
                                paddingAngle={5}
                                dataKey="value"
                            >
                                {[
                                    { name: t('risk.high'), value: stats.highRisk, color: '#ef4444' },
                                    { name: t('risk.medium'), value: stats.mediumRisk, color: '#eab308' },
                                    { name: t('risk.low'), value: stats.lowRisk, color: '#10b981' },
                                ].map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                                ))}
                            </Pie>
                            <Tooltip
                                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }}
                                itemStyle={{ color: '#f1f5f9' }}
                            />
                        </PieChart>
                    </ResponsiveContainer>
                </div>
                <div className="flex justify-center gap-4 mt-4 text-xs">
                    <div className="flex items-center gap-1 text-slate-400">
                        <div className="w-2 h-2 rounded-full bg-red-500" /> {t('risk.high')}
                    </div>
                    <div className="flex items-center gap-1 text-slate-400">
                        <div className="w-2 h-2 rounded-full bg-yellow-500" /> {t('risk.medium')}
                    </div>
                    <div className="flex items-center gap-1 text-slate-400">
                        <div className="w-2 h-2 rounded-full bg-emerald-500" /> {t('risk.low')}
                    </div>
                </div>
            </div>

            {/* Top Processes */}
            <div className="bg-slate-900/50 p-6 rounded-xl border border-slate-800">
                <h3 className="text-sm font-medium text-slate-400 mb-4 flex items-center gap-2">
                    <Settings className="w-4 h-4" />
                    {t('dashboard.top_processes')}
                </h3>
                <div className="space-y-3">
                    {topProcesses.map((proc, i) => (
                        <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-slate-800/50">
                            <div className="w-6 h-6 rounded bg-slate-700 flex items-center justify-center text-xs font-mono text-slate-300">
                                {i + 1}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-sm font-medium text-slate-200 truncate">{proc.name}</span>
                                    <span className="text-xs text-slate-400">{proc.count} {t('dashboard.connections')}</span>
                                </div>
                                <div className="w-full bg-slate-800 rounded-full h-1.5">
                                    <div
                                        className="bg-purple-500 h-1.5 rounded-full transition-all duration-500"
                                        style={{ width: `${(proc.count / Math.max(...topProcesses.map(p => p.count))) * 100}%` }}
                                    />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* World Map */}
            <div className="lg:col-span-1 md:col-span-2">
                {geoIPStatus.exists ? (
                    <WorldMap
                        rows={rows}
                        onCountrySelect={onCountrySelect}
                        selectedCountry={selectedCountry}
                    />
                ) : (
                    <GeoIPManager
                        status={geoIPStatus}
                        onDownload={async () => {
                            const res = await fetch('/api/geoip/download', { method: 'POST' })
                            if (res.ok) {
                                checkGeoIP()
                                window.dispatchEvent(new Event('geoip-status-changed'))
                            }
                        }}
                    />
                )}
            </div>
        </div>
    )
}

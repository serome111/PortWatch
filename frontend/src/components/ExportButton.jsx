import { Download, FileJson, FileSpreadsheet } from 'lucide-react'
import { useState } from 'react'
import { cn } from '../lib/utils'
import { useTranslation } from 'react-i18next'

export function ExportButton({ data, killedProcesses, paranoidMode }) {
    const { t } = useTranslation()
    const [showMenu, setShowMenu] = useState(false)

    const exportToCSV = () => {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
        const filename = `portwatch-export-${timestamp}.csv`

        // CSV Headers
        let csv = 'Type,Timestamp,PID,Process,Level,Score,Reasons,Local Address,Remote Address,Remote Port,Status,Country\n'

        // Add connections
        data.rows?.forEach(row => {
            const reasons = row.reasons?.join('; ') || ''
            const line = [
                'Connection',
                new Date(data.ts * 1000).toISOString(),
                row.pid || '',
                `"${row.proc || ''}"`,
                row.level || '',
                row.score || '',
                `"${reasons}"`,
                row.laddr || '',
                row.raddr || '',
                row.dport || '',
                row.status || '',
                row.country || ''
            ].join(',')
            csv += line + '\n'
        })

        // Add killed processes
        killedProcesses?.forEach(kill => {
            const line = [
                'Killed Process',
                new Date(kill.timestamp * 1000).toISOString(),
                kill.pid || '',
                `"${kill.proc || ''}"`,
                kill.level || kill.type || '',
                kill.score || '',
                `"${kill.reason || ''}"`,
                '',
                kill.raddr || '',
                kill.dport || '',
                'KILLED',
                ''
            ].join(',')
            csv += line + '\n'
        })

        downloadFile(csv, filename, 'text/csv')
        setShowMenu(false)
    }

    const exportToJSON = () => {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
        const filename = `portwatch-export-${timestamp}.json`

        const exportData = {
            export_timestamp: new Date().toISOString(),
            paranoid_mode: paranoidMode,
            connections: {
                timestamp: new Date(data.ts * 1000).toISOString(),
                count: data.rows?.length || 0,
                rows: data.rows || []
            },
            killed_processes: {
                count: killedProcesses?.length || 0,
                processes: killedProcesses || []
            },
            metadata: {
                version: '2.0',
                hostname: window.location.hostname,
                export_type: 'PortWatch Security Report'
            }
        }

        const json = JSON.stringify(exportData, null, 2)
        downloadFile(json, filename, 'application/json')
        setShowMenu(false)
    }

    const downloadFile = (content, filename, mimeType) => {
        const blob = new Blob([content], { type: mimeType })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
    }

    return (
        <div className="relative">
            <button
                onClick={() => setShowMenu(!showMenu)}
                className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
                    "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
                    "hover:border-emerald-500/50 hover:shadow-lg hover:shadow-emerald-500/10"
                )}
            >
                <Download className="w-4 h-4" />
                {t('export.button')}
            </button>

            {showMenu && (
                <>
                    <div
                        className="fixed inset-0 z-40"
                        onClick={() => setShowMenu(false)}
                    />
                    <div className="absolute right-0 mt-2 w-56 bg-slate-900 border border-slate-700 rounded-lg shadow-xl z-50 overflow-hidden">
                        <div className="p-2 border-b border-slate-700 bg-slate-800/50">
                            <p className="text-xs text-slate-400 font-medium">{t('export.format_title')}</p>
                        </div>

                        <button
                            onClick={exportToJSON}
                            className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-800 transition-colors text-left"
                        >
                            <div className="p-2 bg-blue-500/10 rounded-lg border border-blue-500/20">
                                <FileJson className="w-4 h-4 text-blue-400" />
                            </div>
                            <div>
                                <p className="text-sm font-medium text-white">{t('export.json_title')}</p>
                                <p className="text-xs text-slate-400">{t('export.json_desc')}</p>
                            </div>
                        </button>

                        <button
                            onClick={exportToCSV}
                            className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-800 transition-colors text-left"
                        >
                            <div className="p-2 bg-green-500/10 rounded-lg border border-green-500/20">
                                <FileSpreadsheet className="w-4 h-4 text-green-400" />
                            </div>
                            <div>
                                <p className="text-sm font-medium text-white">{t('export.csv_title')}</p>
                                <p className="text-xs text-slate-400">{t('export.csv_desc')}</p>
                            </div>
                        </button>

                        <div className="p-3 bg-slate-800/30 border-t border-slate-700">
                            <p className="text-xs text-slate-500">
                                {t('export.summary', { connections: data.rows?.length || 0, kills: killedProcesses?.length || 0 })}
                            </p>
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}

import { useState, useEffect } from 'react'
import { Globe, Download, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cn } from '../lib/utils'

export function GeoIPManager({ status, onDownload }) {
    const { t } = useTranslation()
    const [downloading, setDownloading] = useState(false)
    const [error, setError] = useState(null)

    const handleDownload = async () => {
        setDownloading(true)
        setError(null)
        try {
            await onDownload()
        } catch (e) {
            console.error(e)
            setError(e.message || t('dashboard.download_error'))
        } finally {
            setDownloading(false)
        }
    }

    if (status.exists) {
        return (
            <div className="flex items-start gap-4 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
                <div className="p-2 bg-emerald-500/20 rounded-lg">
                    <CheckCircle className="w-5 h-5 text-emerald-500" />
                </div>
                <div>
                    <h3 className="text-sm font-medium text-emerald-400 mb-1">{t('dashboard.geoip_active')}</h3>
                    <p className="text-xs text-emerald-500/80">
                        {t('dashboard.geoip_active_desc')}
                    </p>
                </div>
            </div>
        )
    }

    return (
        <div className="bg-slate-900/50 rounded-xl p-6 border border-slate-800">
            <div className="flex items-start gap-4">
                <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                    <Globe className="w-6 h-6 text-blue-500" />
                </div>
                <div className="flex-1">
                    <h3 className="text-lg font-medium text-white mb-2">{t('dashboard.download_geoip')}</h3>
                    <p className="text-sm text-slate-400 mb-4 leading-relaxed">
                        {t('dashboard.download_geoip_desc')}
                    </p>

                    {error && (
                        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                            <AlertCircle className="w-4 h-4" />
                            {error}
                        </div>
                    )}

                    <button
                        onClick={handleDownload}
                        disabled={downloading}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {downloading ? (
                            <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                {t('dashboard.downloading')}
                            </>
                        ) : (
                            <>
                                <Download className="w-4 h-4" />
                                {t('dashboard.download_button')}
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    )
}

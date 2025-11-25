import { useState, useEffect } from 'react'

import { X, Save, Key, ShieldCheck, Globe, List, Bell, AlertTriangle, Check, Trash2, Settings } from 'lucide-react'
import { cn } from '../lib/utils'
import { DNSListsTab } from './DNSListsTab'
import { GeoIPManager } from './GeoIPManager'
import { ConfirmModal } from './ConfirmModal'
import { useTranslation } from 'react-i18next'

export function SettingsModal({ isOpen, onClose }) {
    const { t, i18n } = useTranslation()
    const [activeTab, setActiveTab] = useState('api') // 'api' | 'dns-lists' | 'alerts' | 'geoip'
    const [apiKey, setApiKey] = useState('')
    const [loading, setLoading] = useState(false)
    const [saved, setSaved] = useState(false)
    const [showResetConfirm, setShowResetConfirm] = useState(false)

    // Alert settings
    const [alertSettings, setAlertSettings] = useState({
        enabled: false,
        alert_level: 'high',
        auto_allow_signed: false,
        notification_cooldown: 60
    })
    const [alertLoading, setAlertLoading] = useState(false)
    const [alertSaved, setAlertSaved] = useState(false)

    // GeoIP state
    const [geoIPStatus, setGeoIPStatus] = useState({ exists: false })

    useEffect(() => {
        if (isOpen) {
            // Load API config
            fetch('/api/config')
                .then(res => res.json())
                .then(data => {
                    if (data.abuseipdb_key) setApiKey(data.abuseipdb_key)
                })
                .catch(err => console.error('Error loading config', err))

            // Load alert settings
            fetch('/api/alerts/settings')
                .then(res => res.json())
                .then(data => {
                    if (data.ok && data.settings) {
                        setAlertSettings(data.settings)
                    }
                })
                .catch(e => console.error('Error loading alert settings', e))

            // Load GeoIP status
            fetch('/api/geoip/status')
                .then(res => res.json())
                .then(setGeoIPStatus)
                .catch(e => console.error('Error loading GeoIP status', e))
        }
    }, [isOpen])

    const handleSave = async () => {
        setLoading(true)
        try {
            await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ abuseipdb_key: apiKey })
            })
            setSaved(true)
            setTimeout(() => setSaved(false), 2000)
        } catch (err) {
            console.error('Error saving config', err)
        } finally {
            setLoading(false)
        }
    }


    const handleFactoryReset = async () => {
        try {
            await fetch('/api/factory_reset', { method: 'POST' })
            localStorage.clear()
            window.location.reload()
        } catch (err) {
            console.error('Error resetting:', err)
            alert('Error al restablecer de fábrica')
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <div className="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden">
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                        <Key className="w-5 h-5 text-emerald-400" />
                        {t('settings.title')}
                    </h2>
                    <button onClick={onClose} className="p-1 hover:bg-slate-800 rounded-lg transition-colors">
                        <X className="w-5 h-5 text-slate-400" />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-slate-800 bg-slate-950/50">
                    <button
                        onClick={() => setActiveTab('api')}
                        className={cn(
                            "px-4 py-3 text-sm font-medium transition-all border-b-2 focus:outline-none",
                            activeTab === 'api'
                                ? "border-emerald-500 text-emerald-400"
                                : "border-transparent text-slate-400 hover:text-slate-300"
                        )}
                    >
                        <div className="flex items-center gap-2">
                            <Key className="w-4 h-4" />
                            {t('settings.tabs.api')}
                        </div>
                    </button>
                    <button
                        onClick={() => setActiveTab('dns-lists')}
                        className={cn(
                            "px-4 py-3 text-sm font-medium transition-all border-b-2 focus:outline-none",
                            activeTab === 'dns-lists'
                                ? "border-blue-500 text-blue-400"
                                : "border-transparent text-slate-400 hover:text-slate-300"
                        )}
                    >
                        <div className="flex items-center gap-2">
                            <List className="w-4 h-4" />
                            {t('settings.tabs.dns')}
                        </div>
                    </button>
                    <button
                        onClick={() => setActiveTab('alerts')}
                        className={cn(
                            "px-4 py-3 text-sm font-medium transition-all border-b-2 focus:outline-none",
                            activeTab === 'alerts'
                                ? "border-amber-500 text-amber-400"
                                : "border-transparent text-slate-400 hover:text-slate-300"
                        )}
                    >
                        <div className="flex items-center gap-2">
                            <Bell className="w-4 h-4" />
                            {t('settings.tabs.alerts')}
                        </div>
                    </button>
                    <button
                        onClick={() => setActiveTab('geoip')}
                        className={cn(
                            "px-4 py-3 text-sm font-medium transition-all border-b-2 focus:outline-none",
                            activeTab === 'geoip'
                                ? "border-purple-500 text-purple-400"
                                : "border-transparent text-slate-400 hover:text-slate-300"
                        )}
                    >
                        <div className="flex items-center gap-2">
                            <Globe className="w-4 h-4" />
                            {t('settings.tabs.geoip')}
                        </div>
                    </button>


                    <button
                        onClick={() => setActiveTab('system')}
                        className={cn(
                            "px-4 py-3 text-sm font-medium transition-all border-b-2 focus:outline-none",
                            activeTab === 'system'
                                ? "border-red-500 text-red-400"
                                : "border-transparent text-slate-400 hover:text-slate-300"
                        )}
                    >
                        <div className="flex items-center gap-2">
                            <Settings className="w-4 h-4" />
                            {t('settings.tabs.system')}
                        </div>
                    </button>
                </div>

                {/* Tab Content */}
                <div className="p-6 max-h-[70vh] overflow-y-auto">
                    {activeTab === 'api' && (
                        <div className="space-y-6">
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-slate-300 flex items-center gap-2">
                                    {t('settings.api.abuseipdb_label')}
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">{t('settings.api.free')}</span>
                                </label>
                                <div className="relative">
                                    <input
                                        type="password"
                                        value={apiKey}
                                        onChange={(e) => setApiKey(e.target.value)}
                                        placeholder={t('settings.api.placeholder')}
                                        className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500/50 transition-all"
                                    />
                                    <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
                                </div>
                                <p className="text-xs text-slate-500">
                                    {t('settings.api.help')}
                                </p>
                            </div>

                            <div className="flex justify-end gap-3 pt-2">
                                <button
                                    onClick={handleSave}
                                    disabled={loading || saved}
                                    className={cn(
                                        "px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 transition-all",
                                        saved
                                            ? "bg-emerald-500 text-white"
                                            : "bg-slate-100 text-slate-900 hover:bg-white"
                                    )}
                                >
                                    {saved ? (
                                        <>
                                            <ShieldCheck className="w-4 h-4" />
                                            {t('settings.api.saved')}
                                        </>
                                    ) : (
                                        <>
                                            <Save className="w-4 h-4" />
                                            {loading ? t('settings.api.saving') : t('settings.api.save')}
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    )}

                    {activeTab === 'dns-lists' && <DNSListsTab />}

                    {activeTab === 'alerts' && (
                        <AlertsTab
                            settings={alertSettings}
                            onSettingsChange={setAlertSettings}
                            loading={alertLoading}
                            saved={alertSaved}
                            onSave={async () => {
                                setAlertLoading(true)
                                try {
                                    await fetch('/api/alerts/settings', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify(alertSettings)
                                    })
                                    setAlertSaved(true)
                                    setTimeout(() => setAlertSaved(false), 2000)
                                } catch (err) {
                                    console.error('Error saving alert settings', err)
                                } finally {
                                    setAlertLoading(false)
                                }
                            }}
                        />
                    )}

                    {activeTab === 'geoip' && (
                        <GeoIPManager
                            status={geoIPStatus}
                            onDownload={async () => {
                                const res = await fetch('/api/geoip/download', { method: 'POST' })
                                if (res.ok) {
                                    const newStatus = await fetch('/api/geoip/status').then(r => r.json())
                                    setGeoIPStatus(newStatus)
                                    window.dispatchEvent(new Event('geoip-status-changed'))
                                }
                            }}
                        />
                    )}


                    {activeTab === 'system' && (
                        <div className="space-y-6">
                            {/* Language Selector */}
                            <div className="bg-slate-950 rounded-lg p-6 border border-slate-800">
                                <div className="flex items-start gap-4">
                                    <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                                        <Globe className="w-6 h-6 text-blue-500" />
                                    </div>
                                    <div className="flex-1">
                                        <h3 className="text-lg font-medium text-white mb-2">{t('settings.system.language')}</h3>
                                        <p className="text-sm text-slate-400 mb-4 leading-relaxed">
                                            {t('settings.system.language_desc')}
                                        </p>
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => i18n.changeLanguage('es')}
                                                className={cn(
                                                    "px-4 py-2 text-sm font-medium rounded-lg transition-all focus:outline-none",
                                                    i18n.language === 'es'
                                                        ? "bg-blue-500/30 text-blue-200 shadow-lg shadow-blue-500/20"
                                                        : "bg-slate-800/50 text-slate-400 hover:bg-slate-700/60 hover:text-slate-300"
                                                )}
                                            >
                                                Español
                                            </button>
                                            <button
                                                onClick={() => i18n.changeLanguage('en')}
                                                className={cn(
                                                    "px-4 py-2 text-sm font-medium rounded-lg transition-all focus:outline-none",
                                                    i18n.language === 'en'
                                                        ? "bg-blue-500/30 text-blue-200 shadow-lg shadow-blue-500/20"
                                                        : "bg-slate-800/50 text-slate-400 hover:bg-slate-700/60 hover:text-slate-300"
                                                )}
                                            >
                                                English
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-red-950/20 rounded-lg p-6 border border-red-900/30">
                                <div className="flex items-start gap-4">
                                    <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/20">
                                        <Trash2 className="w-6 h-6 text-red-500" />
                                    </div>
                                    <div className="flex-1">
                                        <h3 className="text-lg font-medium text-white mb-2">{t('settings.system.factory_reset')}</h3>
                                        <p className="text-sm text-slate-400 mb-4 leading-relaxed">
                                            {t('settings.system.factory_reset_desc')}
                                        </p>
                                        <button
                                            onClick={() => setShowResetConfirm(true)}
                                            className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                            {t('settings.system.reset_button')}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <ConfirmModal
                isOpen={showResetConfirm}
                onClose={() => setShowResetConfirm(false)}
                onConfirm={handleFactoryReset}
                title={t('modal.confirm_reset')}
                message={t('modal.reset_message')}
                confirmText={t('modal.yes')}
                cancelText={t('modal.cancel')}
                danger={true}
                type="danger"
            />
        </div >
    )
}



function AlertsTab({ settings, onSettingsChange, loading, saved, onSave }) {
    const { t } = useTranslation()
    const [testing, setTesting] = useState(false)

    const handleTestNotification = async () => {
        setTesting(true)
        try {
            const response = await fetch('/api/alerts/test', { method: 'POST' })
            const data = await response.json()

            if (data.ok) {
                // Success - the backend sent the notification
                console.log('Test notification sent successfully')
            } else {
                alert(t('settings.alerts.error_sending', { error: data.error || 'Unknown error' }))
            }
        } catch (err) {
            console.error('Error testing notification', err)
            alert(t('settings.alerts.error_connection'))
        } finally {
            setTesting(false)
        }
    }

    return (
        <div className="space-y-6">
            {/* Enable/Disable Toggle */}
            <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                        <Bell className="w-4 h-4 text-amber-400" />
                        <span className="text-sm font-medium text-slate-200">{t('settings.alerts.mode_title')}</span>
                    </div>
                    <button
                        onClick={() => onSettingsChange({ ...settings, enabled: !settings.enabled })}
                        className={cn(
                            "relative inline-flex h-6 w-11 items-center justify-start rounded-full transition-all duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-950 p-0.5",
                            settings.enabled ? "bg-amber-500 focus:ring-amber-500/50" : "bg-slate-700 focus:ring-slate-500/50"
                        )}
                    >
                        <span
                            className={cn(
                                "inline-block h-5 w-5 rounded-full bg-white shadow-lg transition-transform duration-200 ease-in-out",
                                settings.enabled ? "translate-x-5" : "translate-x-0"
                            )}
                        />
                    </button>
                </div>
                <p className="text-xs text-slate-500">
                    {t('settings.alerts.mode_desc')}
                </p>
            </div>

            {/* Alert Level */}
            <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                <label className="text-sm font-medium text-slate-200 mb-3 block">
                    {t('settings.alerts.level_title')}
                </label>
                <div className="grid grid-cols-3 gap-2">
                    {[
                        { value: 'all', label: t('settings.alerts.level_all'), color: 'blue', bgActive: 'bg-blue-500/30', textActive: 'text-blue-200', shadowActive: 'shadow-blue-500/20' },
                        { value: 'medium', label: t('settings.alerts.level_medium'), color: 'amber', bgActive: 'bg-amber-500/30', textActive: 'text-amber-200', shadowActive: 'shadow-amber-500/20' },
                        { value: 'high', label: t('settings.alerts.level_high'), color: 'red', bgActive: 'bg-red-500/30', textActive: 'text-red-200', shadowActive: 'shadow-red-500/20' }
                    ].map(({ value, label, bgActive, textActive, shadowActive }) => (
                        <button
                            key={value}
                            onClick={() => onSettingsChange({ ...settings, alert_level: value })}
                            className={cn(
                                "py-2 px-3 text-sm rounded-lg transition-all focus:outline-none",
                                settings.alert_level === value
                                    ? `${bgActive} ${textActive} shadow-lg ${shadowActive}`
                                    : "bg-slate-800/50 text-slate-400 hover:bg-slate-700/60 hover:text-slate-300"
                            )}
                        >
                            {label}
                        </button>
                    ))}
                </div>
                <p className="text-xs text-slate-500 mt-2">
                    {t('settings.alerts.level_desc')}
                </p>
            </div>

            {/* Auto-allow Signed Apps */}
            <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                <div className="flex items-start justify-between">
                    <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                            <ShieldCheck className="w-4 h-4 text-green-400" />
                            <span className="text-sm font-medium text-slate-200">
                                {t('settings.alerts.auto_allow_title')}
                            </span>
                        </div>
                        <p className="text-xs text-slate-500">
                            {t('settings.alerts.auto_allow_desc')}
                        </p>
                    </div>
                    <button
                        onClick={() => onSettingsChange({ ...settings, auto_allow_signed: !settings.auto_allow_signed })}
                        className={cn(
                            "relative inline-flex h-6 w-11 items-center justify-start rounded-full transition-all duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-950 ml-3 flex-shrink-0 p-0.5",
                            settings.auto_allow_signed ? "bg-green-500 focus:ring-green-500/50" : "bg-slate-700 focus:ring-slate-500/50"
                        )}
                    >
                        <span
                            className={cn(
                                "inline-block h-5 w-5 rounded-full bg-white shadow-lg transition-transform duration-200 ease-in-out",
                                settings.auto_allow_signed ? "translate-x-5" : "translate-x-0"
                            )}
                        />
                    </button>
                </div>
            </div>

            {/* Notification Cooldown */}
            <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                <label className="text-sm font-medium text-slate-200 mb-2 block">
                    {t('settings.alerts.cooldown_title', { seconds: settings.notification_cooldown })}
                </label>
                <input
                    type="range"
                    min="10"
                    max="300"
                    step="10"
                    value={settings.notification_cooldown}
                    onChange={(e) => onSettingsChange({ ...settings, notification_cooldown: parseInt(e.target.value) })}
                    className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
                />
                <p className="text-xs text-slate-500 mt-2">
                    {t('settings.alerts.cooldown_desc')}
                </p>
            </div>

            {/* Test Notification */}
            <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                <button
                    onClick={handleTestNotification}
                    disabled={testing}
                    className="w-full py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                    <AlertTriangle className="w-4 h-4" />
                    {testing ? t('settings.alerts.test_button_testing') : t('settings.alerts.test_button')}
                </button>
                <p className="text-xs text-slate-500 mt-2 text-center">
                    {t('settings.alerts.test_desc')}
                </p>
            </div>

            {/* Save Button */}
            <div className="flex justify-end gap-3 pt-2">
                <button
                    onClick={onSave}
                    disabled={loading || saved}
                    className={cn(
                        "px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 transition-all",
                        saved
                            ? "bg-amber-500 text-white"
                            : "bg-slate-100 text-slate-900 hover:bg-white"
                    )}
                >
                    {saved ? (
                        <>
                            <Check className="w-4 h-4" />
                            {t('settings.alerts.saved')}
                        </>
                    ) : (
                        <>
                            <Save className="w-4 h-4" />
                            {loading ? t('settings.alerts.saving') : t('settings.alerts.save_button')}
                        </>
                    )}
                </button>
            </div>
        </div>
    )
}

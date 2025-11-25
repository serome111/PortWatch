import { useState, useEffect } from 'react'
import { X, Plus, Trash2, Shield, AlertTriangle, Globe, Save, Check } from 'lucide-react'
import { cn } from '../lib/utils'
import { useTranslation } from 'react-i18next'

export function DNSListsTab() {
    const { t } = useTranslation()
    const [config, setConfig] = useState({
        whitelist_domains: [],
        whitelist_suffixes: [],
        blacklist_keywords: [],
        blacklist_tlds: []
    })
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [saved, setSaved] = useState(false)

    // Input states
    const [newWhitelistDomain, setNewWhitelistDomain] = useState('')
    const [newWhitelistSuffix, setNewWhitelistSuffix] = useState('')
    const [newBlacklistKeyword, setNewBlacklistKeyword] = useState('')
    const [newBlacklistTLD, setNewBlacklistTLD] = useState('')

    useEffect(() => {
        loadConfig()
    }, [])

    const loadConfig = async () => {
        setLoading(true)
        try {
            const res = await fetch('/api/dns-config')
            const data = await res.json()
            if (data.ok) {
                setConfig(data.config)
            }
        } catch (e) {
            console.error('Error loading DNS config:', e)
        } finally {
            setLoading(false)
        }
    }

    const handleSave = async () => {
        setSaving(true)
        try {
            const res = await fetch('/api/dns-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config })
            })
            const data = await res.json()
            if (data.ok) {
                setSaved(true)
                setTimeout(() => setSaved(false), 2000)
            }
        } catch (e) {
            console.error('Error saving DNS config:', e)
        } finally {
            setSaving(false)
        }
    }

    const addToList = (listKey, value, setter) => {
        if (!value.trim()) return
        setConfig(prev => ({
            ...prev,
            [listKey]: [...new Set([...prev[listKey], value.trim()])]
        }))
        setter('')
    }

    const removeFromList = (listKey, value) => {
        setConfig(prev => ({
            ...prev,
            [listKey]: prev[listKey].filter(item => item !== value)
        }))
    }

    if (loading) {
        return <div className="text-center py-8 text-slate-400">{t('dns.loading')}</div>
    }

    return (
        <div className="space-y-6">
            {/* Whitelist Section */}
            <div className="space-y-4">
                <div className="flex items-center gap-2 pb-2 border-b border-slate-800">
                    <Shield className="w-5 h-5 text-emerald-400" />
                    <h3 className="text-sm font-semibold text-slate-200">{t('dns.whitelist_title')}</h3>
                </div>

                {/* Whitelist Domains */}
                <div className="space-y-2">
                    <label className="text-xs font-medium text-slate-400 uppercase">{t('dns.trusted_domains')}</label>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={newWhitelistDomain}
                            onChange={(e) => setNewWhitelistDomain(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && addToList('whitelist_domains', newWhitelistDomain, setNewWhitelistDomain)}
                            placeholder="ej: google.com"
                            className="flex-1 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500/50"
                        />
                        <button
                            onClick={() => addToList('whitelist_domains', newWhitelistDomain, setNewWhitelistDomain)}
                            className="px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
                        >
                            <Plus className="w-4 h-4" />
                        </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                        {config.whitelist_domains.map((domain) => (
                            <div
                                key={domain}
                                className="flex items-center gap-1.5 px-2 py-1 bg-emerald-900/20 border border-emerald-900/50 rounded text-xs text-emerald-400"
                            >
                                {domain}
                                <button
                                    onClick={() => removeFromList('whitelist_domains', domain)}
                                    className="hover:text-emerald-300"
                                >
                                    <X className="w-3 h-3" />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Whitelist Suffixes */}
                <div className="space-y-2">
                    <label className="text-xs font-medium text-slate-400 uppercase">{t('dns.trusted_suffixes')}</label>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={newWhitelistSuffix}
                            onChange={(e) => setNewWhitelistSuffix(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && addToList('whitelist_suffixes', newWhitelistSuffix, setNewWhitelistSuffix)}
                            placeholder="ej: .yourcompany.com"
                            className="flex-1 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500/50"
                        />
                        <button
                            onClick={() => addToList('whitelist_suffixes', newWhitelistSuffix, setNewWhitelistSuffix)}
                            className="px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
                        >
                            <Plus className="w-4 h-4" />
                        </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                        {config.whitelist_suffixes.map((suffix) => (
                            <div
                                key={suffix}
                                className="flex items-center gap-1.5 px-2 py-1 bg-emerald-900/20 border border-emerald-900/50 rounded text-xs text-emerald-400"
                            >
                                {suffix}
                                <button
                                    onClick={() => removeFromList('whitelist_suffixes', suffix)}
                                    className="hover:text-emerald-300"
                                >
                                    <X className="w-3 h-3" />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Blacklist Section */}
            <div className="space-y-4">
                <div className="flex items-center gap-2 pb-2 border-b border-slate-800">
                    <AlertTriangle className="w-5 h-5 text-red-400" />
                    <h3 className="text-sm font-semibold text-slate-200">{t('dns.blacklist_title')}</h3>
                </div>

                {/* Blacklist Keywords */}
                <div className="space-y-2">
                    <label className="text-xs font-medium text-slate-400 uppercase">{t('dns.suspicious_keywords')}</label>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={newBlacklistKeyword}
                            onChange={(e) => setNewBlacklistKeyword(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && addToList('blacklist_keywords', newBlacklistKeyword, setNewBlacklistKeyword)}
                            placeholder="ej: malware"
                            className="flex-1 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500/50"
                        />
                        <button
                            onClick={() => addToList('blacklist_keywords', newBlacklistKeyword, setNewBlacklistKeyword)}
                            className="px-3 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors"
                        >
                            <Plus className="w-4 h-4" />
                        </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                        {config.blacklist_keywords.map((keyword) => (
                            <div
                                key={keyword}
                                className="flex items-center gap-1.5 px-2 py-1 bg-red-900/20 border border-red-900/50 rounded text-xs text-red-400"
                            >
                                {keyword}
                                <button
                                    onClick={() => removeFromList('blacklist_keywords', keyword)}
                                    className="hover:text-red-300"
                                >
                                    <X className="w-3 h-3" />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Blacklist TLDs */}
                <div className="space-y-2">
                    <label className="text-xs font-medium text-slate-400 uppercase">{t('dns.suspicious_tlds')}</label>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={newBlacklistTLD}
                            onChange={(e) => setNewBlacklistTLD(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && addToList('blacklist_tlds', newBlacklistTLD, setNewBlacklistTLD)}
                            placeholder="ej: .xyz"
                            className="flex-1 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500/50"
                        />
                        <button
                            onClick={() => addToList('blacklist_tlds', newBlacklistTLD, setNewBlacklistTLD)}
                            className="px-3 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors"
                        >
                            <Plus className="w-4 h-4" />
                        </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                        {config.blacklist_tlds.map((tld) => (
                            <div
                                key={tld}
                                className="flex items-center gap-1.5 px-2 py-1 bg-red-900/20 border border-red-900/50 rounded text-xs text-red-400"
                            >
                                {tld}
                                <button
                                    onClick={() => removeFromList('blacklist_tlds', tld)}
                                    className="hover:text-red-300"
                                >
                                    <X className="w-3 h-3" />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Save Button */}
            <div className="flex justify-end pt-4 border-t border-slate-800">
                <button
                    onClick={handleSave}
                    disabled={saving || saved}
                    className={cn(
                        "px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 transition-all",
                        saved
                            ? "bg-emerald-500 text-white"
                            : "bg-blue-600 hover:bg-blue-500 text-white"
                    )}
                >
                    {saved ? (
                        <>
                            <Check className="w-4 h-4" />
                            {t('dns.saved')}
                        </>
                    ) : (
                        <>
                            <Save className="w-4 h-4" />
                            {saving ? t('dns.saving') : t('dns.save_changes')}
                        </>
                    )}
                </button>
            </div>
        </div>
    )
}

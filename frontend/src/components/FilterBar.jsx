import { Search, Filter, Apple, ShieldAlert, Activity } from 'lucide-react'
import { cn } from '../lib/utils'
import { useTranslation } from 'react-i18next'

export function FilterBar({ filters, onFilterChange, paranoidMode, onParanoidModeChange }) {
    const { t } = useTranslation()
    return (
        <div className="flex flex-col sm:flex-row items-center gap-4 mb-6 p-4 bg-slate-900/30 rounded-xl border border-slate-800/50">
            <div className="relative w-full sm:w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                    type="text"
                    placeholder={t('filters.search_placeholder')}
                    value={filters.search}
                    onChange={(e) => onFilterChange({ ...filters, search: e.target.value })}
                    className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all"
                />
            </div>

            <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
                <FilterButton
                    active={filters.hideApple}
                    onClick={() => onFilterChange({ ...filters, hideApple: !filters.hideApple })}
                    icon={Apple}
                    label={t('filters.hide_apple')}
                />
                <FilterButton
                    active={filters.onlyEstablished}
                    onClick={() => onFilterChange({ ...filters, onlyEstablished: !filters.onlyEstablished })}
                    icon={Activity}
                    label={t('filters.only_established')}
                />
                <FilterButton
                    active={filters.highRiskOnly}
                    onClick={() => onFilterChange({ ...filters, highRiskOnly: !filters.highRiskOnly })}
                    icon={ShieldAlert}
                    label={t('filters.only_risk')}
                    activeClass="bg-red-500/10 text-red-400 border-red-500/30"
                />

                <div className="w-px h-6 bg-slate-800 mx-2 hidden sm:block"></div>

                <button
                    onClick={() => onParanoidModeChange(!paranoidMode)}
                    className={cn(
                        "px-3 py-2 rounded-lg text-xs font-medium transition-all flex items-center gap-2 border",
                        paranoidMode
                            ? "bg-red-500 text-white border-red-600 shadow-lg shadow-red-500/20 animate-pulse"
                            : "bg-slate-800/50 text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-slate-300"
                    )}
                    title={t('filters.paranoid_tooltip')}
                >
                    <ShieldAlert className="w-3.5 h-3.5" />
                    {paranoidMode ? t('filters.paranoid_active') : t('filters.paranoid_mode')}
                </button>
            </div>
        </div>
    )
}

function FilterButton({ active, onClick, icon: Icon, label, activeClass }) {
    return (
        <button
            onClick={onClick}
            className={cn(
                "px-3 py-2 rounded-lg text-xs font-medium transition-all flex items-center gap-2 border",
                active
                    ? (activeClass || "bg-emerald-500/10 text-emerald-400 border-emerald-500/30")
                    : "bg-slate-800/50 text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-slate-300"
            )}
        >
            <Icon className="w-3.5 h-3.5" />
            {label}
        </button>
    )
}

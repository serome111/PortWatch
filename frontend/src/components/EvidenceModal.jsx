import { motion, AnimatePresence } from 'framer-motion'
import { X, Info, ShieldAlert, ShieldCheck, Activity, Zap } from 'lucide-react'
import { cn } from '../lib/utils'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'

export function EvidenceModal({ isOpen, onClose, title, description, type = 'info' }) {
    const { t } = useTranslation()
    if (!isOpen) return null

    const icons = {
        info: <Info className="w-6 h-6 text-blue-400" />,
        warning: <ShieldAlert className="w-6 h-6 text-orange-400" />,
        danger: <Activity className="w-6 h-6 text-red-400" />,
        success: <ShieldCheck className="w-6 h-6 text-emerald-400" />,
        mining: <Zap className="w-6 h-6 text-purple-400" />
    }

    const colors = {
        info: "bg-blue-500/10 border-blue-500/20 text-blue-200",
        warning: "bg-orange-500/10 border-orange-500/20 text-orange-200",
        danger: "bg-red-500/10 border-red-500/20 text-red-200",
        success: "bg-emerald-500/10 border-emerald-500/20 text-emerald-200",
        mining: "bg-purple-500/10 border-purple-500/20 text-purple-200"
    }

    const modalContent = (
        <AnimatePresence>
            <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
                <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: 10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: 10 }}
                    onClick={e => e.stopPropagation()}
                    className={cn(
                        "w-full max-w-md rounded-xl border p-6 pr-12 shadow-2xl relative overflow-hidden",
                        "bg-slate-900 border-slate-800"
                    )}
                >
                    {/* Background Glow */}
                    <div className={cn("absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-current to-transparent opacity-50",
                        type === 'danger' ? 'text-red-500' :
                            type === 'warning' ? 'text-orange-500' :
                                type === 'mining' ? 'text-purple-500' : 'text-blue-500'
                    )} />

                    <button
                        onClick={onClose}
                        className="absolute top-4 right-4 p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>

                    <div className="flex items-start gap-4">
                        <div className={cn("p-3 rounded-lg border", colors[type])}>
                            {icons[type] || icons.info}
                        </div>
                        <div className="space-y-2">
                            <h3 className="text-lg font-semibold text-white leading-none pt-1">
                                {title}
                            </h3>
                            <p className="text-sm text-slate-300 leading-relaxed">
                                {description}
                            </p>
                        </div>
                    </div>

                    <div className="mt-6 flex justify-end">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors"
                        >
                            {t('modal.understood')}
                        </button>
                    </div>
                </motion.div>
            </div>
        </AnimatePresence>
    )

    // Render modal using Portal to escape table DOM hierarchy
    return createPortal(modalContent, document.body)
}

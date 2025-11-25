import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, CheckCircle, Info, X } from 'lucide-react'
import { cn } from '../lib/utils'

/**
 * Custom confirmation/alert modal to replace ugly browser alerts
 * 
 * Types:
 * - confirm: Yes/No buttons
 * - alert: Single OK button
 * - success: Success message with OK button
 */
export function ConfirmModal({
    isOpen,
    onClose,
    onConfirm,
    title,
    message,
    type = 'confirm',
    confirmText = 'Confirmar',
    cancelText = 'Cancelar',
    danger = false
}) {
    if (!isOpen) return null

    const handleConfirm = () => {
        if (onConfirm) onConfirm()
        onClose()
    }

    const handleCancel = () => {
        onClose()
    }

    const icons = {
        confirm: <AlertTriangle className="w-6 h-6 text-yellow-400" />,
        alert: <Info className="w-6 h-6 text-blue-400" />,
        success: <CheckCircle className="w-6 h-6 text-emerald-400" />,
        danger: <AlertTriangle className="w-6 h-6 text-red-400" />
    }

    const iconColors = {
        confirm: "bg-yellow-500/10 border-yellow-500/20",
        alert: "bg-blue-500/10 border-blue-500/20",
        success: "bg-emerald-500/10 border-emerald-500/20",
        danger: "bg-red-500/10 border-red-500/20"
    }

    const actualType = danger ? 'danger' : type

    return (
        <AnimatePresence>
            <div
                className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
                onClick={handleCancel}
            >
                <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: 10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: 10 }}
                    transition={{ duration: 0.15 }}
                    onClick={e => e.stopPropagation()}
                    className={cn(
                        "w-full max-w-md rounded-xl border p-6 shadow-2xl relative overflow-hidden",
                        "bg-slate-900 border-slate-700"
                    )}
                >
                    {/* Top accent bar */}
                    <div className={cn(
                        "absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-current to-transparent opacity-50",
                        actualType === 'danger' ? 'text-red-500' :
                            actualType === 'confirm' ? 'text-yellow-500' :
                                actualType === 'success' ? 'text-emerald-500' : 'text-blue-500'
                    )} />

                    <button
                        onClick={handleCancel}
                        className="absolute top-4 right-4 p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>

                    <div className="flex items-start gap-4 mb-6">
                        <div className={cn("p-3 rounded-lg border", iconColors[actualType])}>
                            {icons[actualType]}
                        </div>
                        <div className="flex-1 pt-1">
                            <h3 className="text-lg font-semibold text-white mb-2">
                                {title}
                            </h3>
                            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
                                {message}
                            </p>
                        </div>
                    </div>

                    <div className="flex gap-3 justify-end">
                        {type === 'confirm' && (
                            <button
                                onClick={handleCancel}
                                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors"
                            >
                                {cancelText}
                            </button>
                        )}
                        <button
                            onClick={handleConfirm}
                            className={cn(
                                "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
                                danger
                                    ? "bg-red-600 hover:bg-red-500 text-white"
                                    : type === 'success'
                                        ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                                        : "bg-blue-600 hover:bg-blue-500 text-white"
                            )}
                        >
                            {type === 'confirm' ? confirmText : 'Entendido'}
                        </button>
                    </div>
                </motion.div>
            </div>
        </AnimatePresence>
    )
}

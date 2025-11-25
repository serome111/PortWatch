import { Copy, Check } from 'lucide-react'
import { useState } from 'react'
import { cn } from '../lib/utils'

export function CopyButton({ text, className }) {
    const [copied, setCopied] = useState(false)

    const handleCopy = (e) => {
        e.stopPropagation()
        navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    return (
        <button
            onClick={handleCopy}
            className={cn(
                "p-1 rounded hover:bg-slate-700/50 transition-colors group",
                className
            )}
            title="Copiar al portapapeles"
        >
            {copied ? (
                <Check className="w-3 h-3 text-emerald-400" />
            ) : (
                <Copy className="w-3 h-3 text-slate-500 group-hover:text-slate-300" />
            )}
        </button>
    )
}

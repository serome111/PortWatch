import { useState, useEffect } from 'react'
import { Box } from 'lucide-react'

export function ProcessIcon({ pid, className }) {
    const [iconSrc, setIconSrc] = useState(null)
    const [error, setError] = useState(false)

    useEffect(() => {
        let active = true
        let objectUrl = null

        const loadIcon = async () => {
            try {
                const res = await fetch(`/api/icon/${pid}`)
                if (!res.ok) throw new Error('No icon')

                // Check if backend returned a real icon or the transparent placeholder
                const iconFound = res.headers.get('X-Icon-Found')
                if (iconFound === 'false') throw new Error('No icon')

                const blob = await res.blob()
                if (active) {
                    objectUrl = URL.createObjectURL(blob)
                    setIconSrc(objectUrl)
                    setError(false)
                }
            } catch (err) {
                if (active) setError(true)
            }
        }

        loadIcon()

        return () => {
            active = false
            if (objectUrl) URL.revokeObjectURL(objectUrl)
        }
    }, [pid])

    if (error || !iconSrc) {
        return <Box className={`text-slate-600 ${className}`} />
    }

    return (
        <img
            src={iconSrc}
            alt=""
            className={`object-contain ${className}`}
            onError={() => setError(true)}
        />
    )
}

import { useState } from 'react'
import { cn } from '../lib/utils'
import { EvidenceModal } from './EvidenceModal'
import { useTranslation } from 'react-i18next'

const SENSITIVE_PORTS = new Set([22, 23, 25, 445, 3389, 5900])
const MINING_PORTS = new Set([3333, 4444])
const TOR_PORTS = new Set(Array.from({ length: 30 }, (_, i) => 9001 + i))

function isPublicIp(host) {
    if (!host) return false
    if (host.startsWith('127.') || host === '::1') return false
    if (host.startsWith('10.') || host.startsWith('192.168.') || /^172\.(1[6-9]|2\d|3[01])\./.test(host)) return false
    return true
}

export function Chips({ row }) {
    const { t } = useTranslation()
    const [modalInfo, setModalInfo] = useState(null)
    const chips = []
    const exe = (row.exe || '').toLowerCase()
    const host = (row.raddr || '').split(':')[0]
    const port = Number(row.dport)

    // Helper to get evidence type (for modal styling)
    const getEvidenceType = (id) => {
        const typeMap = {
            tmp: 'warning', sensitive: 'danger', mining: 'mining', tor: 'danger',
            public_ip: 'info', recent: 'warning', beacon: 'danger', unsigned: 'warning',
            apple: 'success', quarantine: 'warning', abuse: 'danger', many_dsts: 'warning',
            high_cpu: 'danger', high_ram: 'warning', parent: 'danger', dns_risk: 'danger',
            risky_country: 'warning', closed: 'info', ransomware: 'danger'
        }
        return typeMap[id] || 'info'
    }

    const add = (id, label, className, fallbackTitle) => {
        // Try to get from narratives.evidence, otherwise use fallback
        const hasTranslation = t(`narratives.evidence.${id}.title`, { defaultValue: '' })
        const info = hasTranslation ? {
            title: t(`narratives.evidence.${id}.title`),
            desc: t(`narratives.evidence.${id}.desc`),
            type: getEvidenceType(id)
        } : { title: fallbackTitle, desc: fallbackTitle, type: 'info' }

        chips.push(
            <button
                key={label + id}
                onClick={(e) => {
                    e.stopPropagation()
                    setModalInfo({ ...info, title: info.title || fallbackTitle })
                }}
                className={cn(
                    "inline-block px-2 py-0.5 rounded-full text-[10px] font-medium border hover:scale-105 transition-transform cursor-pointer",
                    className
                )}
                title={t('chips.click_explanation')}
            >
                {label}
            </button>
        )
    }

    // /tmp hints
    if (exe.includes('/tmp') || exe.includes('/private/tmp') || exe.includes('/var/tmp') || exe.includes('/dev/shm')) {
        add('tmp', '/tmp', 'bg-orange-500/10 text-orange-400 border-orange-500/20', 'Ejecutable en carpeta temporal')
    }

    // Ports
    if (SENSITIVE_PORTS.has(port)) {
        add('sensitive', `:${port}`, 'bg-red-500/10 text-red-400 border-red-500/20', 'Puerto sensible')
    }
    if (MINING_PORTS.has(port)) {
        add('mining', t('chips.mining'), 'bg-purple-500/10 text-purple-400 border-purple-500/20', 'Puerto típico de minería')
    }
    if (TOR_PORTS.has(port)) {
        add('tor', t('chips.tor'), 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20', 'Puerto típico de Tor')
    }

    // Public IP
    if (isPublicIp(host)) {
        add('public_ip', t('chips.public_ip'), 'bg-sky-500/10 text-sky-400 border-sky-500/20', 'Conexión hacia Internet')
    }

    // Recent binary + public IP
    if (row.exe_recent && isPublicIp(host)) {
        add('recent', t('chips.recent'), 'bg-teal-500/10 text-teal-400 border-teal-500/20', 'Binario reciente con salida')
    }

    // Beacon
    if (row.beacon) {
        add('beacon', 'beacon', 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20', 'Patrón repetitivo de conexión')
    }

    // RANSOMWARE Detection (check reasons for RANSOMWARE keyword)
    const hasRansomwareIndicator = (row.reasons || []).some(r => r.includes('RANSOMWARE'))
    if (hasRansomwareIndicator) {
        add('ransomware', '🚨 RANSOMWARE', 'bg-red-500/30 text-red-200 border-red-500/60 animate-pulse ring-2 ring-red-500/50', 'Posible actividad de ransomware detectada')
    }

    // DNS Risk (NUEVO - Prioridad alta)
    const dnsRisk = row.dns_risk
    if (dnsRisk && dnsRisk.score > 0) {
        const label = dnsRisk.score >= 60 ? `DNS: ${dnsRisk.score.toFixed(0)}%` :
            dnsRisk.score >= 30 ? `DNS: ${dnsRisk.score.toFixed(0)}%` :
                `DNS: ${dnsRisk.score.toFixed(0)}%`

        const className = dnsRisk.score >= 60
            ? 'bg-red-500/20 text-red-300 border-red-500/40 animate-pulse'
            : dnsRisk.score >= 30
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'

        add('dns_risk', label, className,
            `Riesgo DNS: ${dnsRisk.reasons.join(', ')}`)
    }

    // High-risk countries
    const HIGH_RISK_COUNTRIES = new Set(['RU', 'CN', 'KP', 'IR', 'SY', 'BY'])
    if (row.country && HIGH_RISK_COUNTRIES.has(row.country)) {
        add('risky_country', `📍 ${row.country}`,
            'bg-red-500/10 text-red-400 border-red-500/20',
            `Conexión a país de alto riesgo: ${row.country_name || row.country}`)
    }

    // CLOSED status
    if (row.status === 'CLOSED') {
        add('closed', t('chips.closed'),
            'bg-slate-600/20 text-slate-400 border-slate-600/40',
            'Conexión cerrada recientemente')
    }

    // Signature
    if (!row.signed) {
        add('unsigned', t('chips.unsigned'), 'bg-rose-500/10 text-rose-400 border-rose-500/20', 'Aplicación sin firma')
    } else if (row.apple) {
        const label = row.notarized ? t('chips.apple_verified') : t('chips.apple')
        const title = row.notarized ? 'Aplicación de Apple notariada' : 'Aplicación de Apple'
        add('apple', label, 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', title)
    }

    if (row.quarantine) {
        add('quarantine', t('chips.quarantine'), 'bg-rose-500/10 text-rose-400 border-rose-500/20', 'Descargado recientemente')
    }

    // Suspicious parent spawn
    if (row.suspicious_parent) {
        const parentName = row.parent_name || 'script'
        add('parent', `↳ ${parentName}`, 'bg-red-500/10 text-red-400 border-red-500/20 animate-pulse', `Lanzado por proceso sospechoso: ${parentName}`)
    }

    // AbuseIPDB Score
    if (row.abuse_score > 0) {
        chips.push(
            <button
                key="abuse"
                onClick={(e) => {
                    e.stopPropagation()
                    setModalInfo({
                        title: t('narratives.evidence.abuse.title'),
                        desc: t('narratives.evidence.abuse.desc'),
                        type: 'danger'
                    })
                }}
                className={cn(
                    "inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ring-1 hover:scale-105 transition-transform cursor-pointer",
                    row.abuse_score >= 80 ? "bg-red-500/20 text-red-300 ring-red-500/50" :
                        row.abuse_score >= 50 ? "bg-orange-500/20 text-orange-300 ring-orange-500/50" :
                            "bg-yellow-500/20 text-yellow-300 ring-yellow-500/50"
                )}
                title={t('chips.click_explanation')}
            >
                {t('chips.abuse')}: {row.abuse_score}%
            </button>
        )
    }

    // Unique dsts
    if ((row.unique_dsts || 0) >= 10) {
        add('many_dsts', '10+ dsts', 'bg-fuchsia-500/10 text-fuchsia-400 border-fuchsia-500/20', 'Muchos destinos distintos')
    } else if ((row.unique_dsts || 0) >= 5) {
        add('many_dsts', '5+ dsts', 'bg-fuchsia-500/10 text-fuchsia-400 border-fuchsia-500/20', 'Varios destinos distintos')
    }

    // Resource Usage
    const cpu = row.cpu || 0
    const mem = row.mem || 0

    if (cpu > 50) {
        add('high_cpu', `CPU: ${cpu.toFixed(0)}%`, 'bg-red-500/20 text-red-300 border-red-500/40 animate-pulse', 'Alto consumo de CPU')
    }

    if (mem > 524288000) { // 500MB
        const memMB = (mem / (1024 * 1024)).toFixed(0)
        add('high_ram', `RAM: ${memMB}MB`, 'bg-orange-500/20 text-orange-300 border-orange-500/40', 'Alto consumo de RAM')
    }

    return (
        <>
            <div className="flex flex-wrap gap-1">{chips}</div>
            <EvidenceModal
                isOpen={!!modalInfo}
                onClose={() => setModalInfo(null)}
                title={modalInfo?.title}
                description={modalInfo?.desc}
                type={modalInfo?.type}
            />
        </>
    )
}

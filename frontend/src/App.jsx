import { useEffect, useState, useRef } from 'react'
import { Activity, AlertTriangle, Bell, ShieldOff, ArrowDown, ArrowUp, Info } from 'lucide-react'
import { cn } from './lib/utils'
import { Dashboard } from './components/Dashboard'
import { ConnectionTable } from './components/ConnectionTable'
import { FilterBar } from './components/FilterBar'
import { SettingsModal } from './components/SettingsModal'
import { KilledProcessesBar } from './components/KilledProcessesBar'
import { ExportButton } from './components/ExportButton'
import { Settings } from 'lucide-react'
import { AlertsPanel } from './components/AlertsPanel'
import { BlockedProcessesPanel } from './components/BlockedProcessesPanel'
import { useTranslation } from 'react-i18next'
import { EvidenceModal } from './components/EvidenceModal'

function formatBytes(bytes, decimals = 1) {
  if (!+bytes) return '0 B'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

function App() {
  const { t } = useTranslation()
  const [connected, setConnected] = useState(false)
  const [data, setData] = useState({ rows: [], ts: 0 })
  const [lastUpdate, setLastUpdate] = useState(null)
  const [paranoidMode, setParanoidMode] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [killedProcesses, setKilledProcesses] = useState([])
  const [filters, setFilters] = useState(() => {
    // Load filters from localStorage if available
    const saved = localStorage.getItem('portwatch_filters')
    return saved ? JSON.parse(saved) : {
      search: '',
      hideApple: false,
      onlyEstablished: false,
      highRiskOnly: false
    }
  })
  const [selectedCountry, setSelectedCountry] = useState(null)
  const [pendingAlerts, setPendingAlerts] = useState([])
  const [showAlerts, setShowAlerts] = useState(false)
  const lastAlertCount = useRef(0)
  const [blockedRules, setBlockedRules] = useState([])
  const [showBlockedPanel, setShowBlockedPanel] = useState(false)
  const [showTrafficInfo, setShowTrafficInfo] = useState(false)

  // Save filters to localStorage
  useEffect(() => {
    localStorage.setItem('portwatch_filters', JSON.stringify(filters))
  }, [filters])

  // Sync Paranoid Mode with backend
  useEffect(() => {
    fetch('/api/get_paranoid_mode')
      .then(res => res.json())
      .then(data => {
        if (data.paranoid_mode !== undefined) {
          setParanoidMode(data.paranoid_mode)
        }
      })
      .catch(e => console.error("Failed to get paranoid mode", e))
  }, [])

  // Fetch and store auth token
  useEffect(() => {
    fetch('/api/token')
      .then(res => res.json())
      .then(data => {
        if (data.token) {
          // Store token in cookie for authentication
          document.cookie = `pwtoken=${data.token}; path=/; SameSite=Strict`
        }
      })
      .catch(e => console.error("Failed to get auth token", e))
  }, [])

  // Fetch blocked rules periodically
  useEffect(() => {
    const fetchBlockedRules = async () => {
      try {
        const response = await fetch('/api/rules')
        const data = await response.json()
        if (data.ok) {
          // Filter only deny rules that are enabled
          const denied = data.rules.filter(r => r.action === 'deny' && r.enabled)
          setBlockedRules(denied)
        }
      } catch (e) {
        console.error("Failed to fetch rules", e)
      }
    }

    fetchBlockedRules()
    const interval = setInterval(fetchBlockedRules, 5000) // Update every 5s
    return () => clearInterval(interval)
  }, [])

  const handleParanoidModeChange = async (newValue) => {
    try {
      await fetch(`/api/set_paranoid_mode?enabled=${newValue}`, { method: 'POST' })
      setParanoidMode(newValue)
    } catch (e) {
      console.error("Failed to set paranoid mode", e)
    }
  }


  const handleClearKilled = async () => {
    try {
      await fetch('/api/clear_killed_history', { method: 'POST' })
      setKilledProcesses([])
    } catch (e) {
      console.error("Failed to clear killed history", e)
    }
  }

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    // In dev, vite proxy handles /ws -> ws://localhost:8000/ws
    // In prod, it's same origin
    const wsUrl = `${protocol}//${host}/ws`

    let ws = null;
    let retryTimeout = null;

    const connect = () => {
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('WebSocket Connected')
        setConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)

          // Session History Logic
          setData(prevData => {
            const currentRows = msg.rows || []
            const prevRows = prevData.rows || [] // This now contains ONLY active rows from previous state
            const prevHistory = prevData.history || [] // This contains closed rows
            const now = Date.now()

            // 1. Identify newly closed connections
            // A connection is closed if it was in prevRows but is NOT in currentRows
            const currentIds = new Set(currentRows.map(r => r.pid + '-' + r.raddr))
            const newlyClosed = prevRows.filter(r =>
              !currentIds.has(r.pid + '-' + r.raddr)
            ).map(r => ({
              ...r,
              status: 'CLOSED',
              closedAt: now
            }))

            // 2. Update History
            // Add newly closed to history
            // Remove from history if they reappear in currentRows (reconnected)
            let newHistory = [...prevHistory, ...newlyClosed]
            newHistory = newHistory.filter(r => !currentIds.has(r.pid + '-' + r.raddr))

            // Sort history by closedAt desc
            newHistory.sort((a, b) => b.closedAt - a.closedAt)

            return {
              ...msg,
              rows: currentRows, // Only active rows here
              history: newHistory // Only closed rows here
            }
          })

          setLastUpdate(new Date())
          // Update killed processes if provided
          if (msg.killed_processes) {
            setKilledProcesses(msg.killed_processes)
          }
          // Update pending alerts if provided
          if (msg.pending_alerts) {
            setPendingAlerts(msg.pending_alerts)

            // Auto-show alerts panel ONLY if there are NEW alerts
            // We compare with the previous length tracked in a ref
            if (msg.pending_alerts.length > lastAlertCount.current) {
              setShowAlerts(true)
            }
            lastAlertCount.current = msg.pending_alerts.length
          }
        } catch (e) {
          console.error('Error parsing WS message', e)
        }
      }

      ws.onclose = () => {
        console.log('WebSocket Disconnected')
        setConnected(false)
        // Retry connection
        retryTimeout = setTimeout(connect, 3000)
      }

      ws.onerror = (err) => {
        console.error('WebSocket Error', err)
        ws.close()
      }
    }

    connect()

    return () => {
      if (ws) ws.close()
      if (retryTimeout) clearTimeout(retryTimeout)
    }
  }, [])

  // Filter logic
  const [viewMode, setViewMode] = useState('active') // 'active' | 'history'

  const sourceRows = viewMode === 'active' ? data.rows : (data.history || [])

  const filteredRows = sourceRows.filter(row => {
    // Search
    if (filters.search) {
      const q = filters.search.toLowerCase()
      const match =
        row.proc?.toLowerCase().includes(q) ||
        String(row.pid).includes(q) ||
        row.raddr?.toLowerCase().includes(q) ||
        row.user?.toLowerCase().includes(q)
      if (!match) return false
    }

    // Hide Apple
    if (filters.hideApple && row.apple) return false

    // Only Established (ESTABLISHED) - Only apply to Active view
    if (viewMode === 'active' && filters.onlyEstablished && row.status !== 'ESTABLISHED') return false

    // High Risk Only (Medium or High)
    if (filters.highRiskOnly && row.level === 'bajo') return false

    // Country Filter
    if (selectedCountry && row.country !== selectedCountry) return false

    return true
  })

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-blue-500/30">
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-slate-950 to-black -z-10" />

      <SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} />

      <header className="border-b border-slate-800/60 bg-slate-950/50 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="absolute inset-0 bg-blue-500 blur-lg opacity-20 animate-pulse" />
              <svg
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="w-8 h-8 text-blue-500 relative z-10 animate-pulse"
              >
                <path
                  d="M2 12C4.5 7.5 8 5 12 5C16 5 19.5 7.5 22 12C19.5 16.5 16 19 12 19C8 19 4.5 16.5 2 12Z"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <circle
                  cx="12"
                  cy="12"
                  r="2.3"
                  fill="currentColor"
                />
              </svg>
            </div>
            <div>
              <h1 className="font-bold text-xl tracking-tight bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
                PortWatch
              </h1>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className={cn("w-2 h-2 rounded-full", connected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-red-500")} />
                {connected ? t('dashboard.monitor_active') : t('dashboard.disconnected')}
                {data.net_speed && (
                  <>
                    <span className="mx-1 text-slate-700">|</span>
                    <div className="flex items-center gap-3 font-mono text-xs">
                      <div className="flex items-center gap-1 text-slate-500 font-medium">
                        <span>{t('header.network_traffic')}:</span>
                        <button
                          onClick={() => setShowTrafficInfo(true)}
                          className="p-1 rounded-full hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                          title={t('header.network_tooltip')}
                        >
                          <Info className="w-4 h-4" />
                        </button>
                      </div>
                      <span
                        className="flex items-center gap-1 text-emerald-400"
                        title={t('dashboard.download')}
                      >
                        <ArrowDown className="w-3 h-3" />
                        {formatBytes(data.net_speed.down)}/s
                      </span>
                      <span
                        className="flex items-center gap-1 text-blue-400"
                        title={t('dashboard.upload')}
                      >
                        <ArrowUp className="w-3 h-3" />
                        {formatBytes(data.net_speed.up)}/s
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Alert Badge */}
            {pendingAlerts.length > 0 && (
              <button
                onClick={() => setShowAlerts(!showAlerts)}
                className="relative p-2 hover:bg-amber-900/20 rounded-lg transition-colors text-amber-400 hover:text-amber-300"
              >
                <Bell className="w-5 h-5 animate-pulse" />
                <span className="absolute -top-1 -right-1 bg-amber-500 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center shadow-lg">
                  {pendingAlerts.length}
                </span>
              </button>
            )}
            {/* Blocked Processes Badge */}
            {blockedRules.length > 0 && (
              <button
                onClick={() => setShowBlockedPanel(!showBlockedPanel)}
                className="relative p-2 hover:bg-red-900/20 rounded-lg transition-colors text-red-400 hover:text-red-300"
                title={t('sidebar.blocked')}
              >
                <ShieldOff className="w-5 h-5" />
                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center shadow-lg">
                  {blockedRules.length}
                </span>
              </button>
            )}
            {paranoidMode && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium animate-pulse">
                <AlertTriangle className="w-3 h-3" />
                {t('sidebar.paranoid')}
              </div>
            )}
            <ExportButton
              data={data}
              killedProcesses={killedProcesses}
              paranoidMode={paranoidMode}
            />
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 hover:bg-slate-800 rounded-lg transition-colors text-slate-400 hover:text-slate-200"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      <EvidenceModal
        isOpen={showTrafficInfo}
        onClose={() => setShowTrafficInfo(false)}
        title={t('header.network_info_title')}
        description={t('header.network_info_desc')}
        type="info"
      />

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        <Dashboard
          rows={data.rows}
          onCountrySelect={setSelectedCountry}
          selectedCountry={selectedCountry}
          data={data}
          onCountryClick={setSelectedCountry}
        />

        {/* Killed Processes Bar */}
        <KilledProcessesBar
          killedProcesses={killedProcesses}
          onClear={handleClearKilled}
        />

        <div className={cn(
          "rounded-xl border p-6 backdrop-blur-sm transition-colors duration-500",
          paranoidMode ? "bg-red-950/10 border-red-900/30" : "bg-slate-900/50 border-slate-800"
        )}>
          <div className="flex flex-col sm:flex-row items-center justify-between mb-6 gap-4">
            <div className="flex items-center gap-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Activity className="w-5 h-5 text-slate-400" />
                {t('dashboard.connections')}
              </h2>

              {/* View Mode Tabs */}
              <div className="flex items-center bg-slate-900/50 rounded-lg p-1 border border-slate-800">
                <button
                  onClick={() => setViewMode('active')}
                  className={cn(
                    "px-3 py-1 text-xs font-medium rounded-md transition-all",
                    viewMode === 'active'
                      ? "bg-slate-700 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-300"
                  )}
                >
                  {t('dashboard.active')} ({data.rows?.length || 0})
                </button>
                <button
                  onClick={() => setViewMode('history')}
                  className={cn(
                    "px-3 py-1 text-xs font-medium rounded-md transition-all",
                    viewMode === 'history'
                      ? "bg-slate-700 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-300"
                  )}
                >
                  {t('dashboard.history')} ({data.history?.length || 0})
                </button>
              </div>

              {selectedCountry && (
                <button
                  onClick={() => setSelectedCountry(null)}
                  className="px-2 py-1 bg-blue-500/20 text-blue-400 text-xs rounded-full border border-blue-500/30 hover:bg-blue-500/30 transition-colors flex items-center gap-1"
                >
                  {t('dashboard.filter')}: {selectedCountry} ✕
                </button>
              )}
            </div>
          </div>

          <FilterBar
            filters={filters}
            onFilterChange={setFilters}
            paranoidMode={paranoidMode}
            onParanoidModeChange={handleParanoidModeChange}
          />

          <ConnectionTable rows={filteredRows} paranoidMode={paranoidMode} />
        </div>
      </main>

      {/* Alerts Panel */}
      {showAlerts && pendingAlerts.length > 0 && (
        <AlertsPanel
          alerts={pendingAlerts}
          onClose={() => setShowAlerts(false)}
          onDecide={async (alertId, action, scope) => {
            try {
              const response = await fetch(`/api/alerts/${alertId}/decide`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, scope })
              })
              const data = await response.json()
              if (data.ok) {
                // Remove the alert from pending list
                setPendingAlerts(prev => prev.filter(a => a.id !== alertId))
                // Close panel if no more alerts
                if (pendingAlerts.length === 1) {
                  setShowAlerts(false)
                }
              }
            } catch (err) {
              console.error('Error deciding alert:', err)
            }
          }}
        />
      )}

      {/* Blocked Processes Panel */}
      {showBlockedPanel && blockedRules.length > 0 && (
        <BlockedProcessesPanel
          rules={blockedRules}
          onClose={() => setShowBlockedPanel(false)}
          onUnblock={async (ruleId) => {
            try {
              const response = await fetch(`/api/rules/${ruleId}`, {
                method: 'DELETE'
              })
              const data = await response.json()
              if (data.ok) {
                // Remove from local state
                setBlockedRules(prev => prev.filter(r => r.id !== ruleId))
              }
            } catch (err) {
              console.error('Error unblocking:', err)
            }
          }}
        />
      )}
    </div>
  )
}

export default App

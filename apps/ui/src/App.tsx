import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { buildScene, type Patch, type SceneActor } from './runtime/sceneRuntime'

declare const __OPENCOMMOTION_UI_VERSION__: string

type VoiceSegment = {
  text: string
  start_ms: number
  duration_ms: number
  audio_uri: string
}

type VoicePayload = {
  voice: string
  engine?: string
  segments: VoiceSegment[]
}

type QualityReport = {
  ok: boolean
  checks: string[]
  warnings: string[]
  failures: string[]
}

type TurnResult = {
  session_id: string
  turn_id: string
  text: string
  voice: VoicePayload
  visual_patches: Patch[]
  timeline?: { duration_ms: number }
  quality_report?: QualityReport
}

type ArtifactResult = {
  artifact_id: string
  title: string
  score?: number
  match_mode?: string
}

type VoiceEngineDetails = {
  selected_engine?: string
  strict_real_engines?: boolean
  [key: string]: unknown
}

type LlmCapabilities = {
  selected_provider?: string
  effective_provider?: string
  active_provider_ready?: boolean
  effective_ready?: boolean
  allow_fallback?: boolean
  message?: string
}

type RuntimeCapabilities = {
  llm: LlmCapabilities
  voice: {
    stt: VoiceEngineDetails
    tts: VoiceEngineDetails
  }
}

type SetupStateResponse = {
  state: Record<string, string>
  editable_keys: string[]
}

type SetupValidateResponse = {
  ok: boolean
  errors: string[]
  warnings: string[]
}

type AgentRun = {
  run_id: string
  session_id: string
  label: string
  status: string
  auto_run: boolean
  last_error: string
  queue?: {
    queued: number
    processing: number
    done: number
    error: number
  }
}

type AgentLogEntry = {
  id: string
  at: string
  event_type: string
  message: string
}

const gateway = (import.meta as { env?: Record<string, string> }).env?.VITE_GATEWAY_URL || 'http://127.0.0.1:8000'
const wsGateway = gateway.replace(/^http/i, 'ws')
const gatewayApiKey =
  (import.meta as { env?: Record<string, string> }).env?.VITE_GATEWAY_API_KEY || 'dev-opencommotion-key'
const isTestMode = (import.meta as { env?: Record<string, string> }).env?.MODE === 'test'
const uiVersion = __OPENCOMMOTION_UI_VERSION__

function calcDurationMs(turn: TurnResult): number {
  const patchEnd = turn.visual_patches.reduce((max, patch) => {
    const atMs = patch.at_ms || 0
    return atMs > max ? atMs : max
  }, 0)
  return Math.max(turn.timeline?.duration_ms || 0, patchEnd + 200)
}

function describeMotion(actor: SceneActor): string {
  if (!actor.motion) {
    return ''
  }
  if (typeof actor.motion === 'string') {
    return actor.motion
  }
  return actor.motion.name
}

function mapPolyline(points: number[][], x: number, y: number, width: number, height: number): string {
  return points
    .map(([px, py]) => {
      const sx = x + (px / 100) * width
      const sy = y + (py / 100) * height
      return `${sx},${sy}`
    })
    .join(' ')
}

function parseStylePoints(style: Record<string, unknown>): number[][] {
  const raw = style.points
  if (!Array.isArray(raw)) {
    return []
  }
  return raw
    .filter((row): row is number[] => Array.isArray(row) && row.length >= 2)
    .map((row) => [Number(row[0]), Number(row[1]), Number(row[2] || 0)])
    .filter((row) => Number.isFinite(row[0]) && Number.isFinite(row[1]))
}

function describeVoice(voice: VoicePayload | null): string {
  if (!voice) {
    return 'No voice output yet.'
  }
  return `${voice.voice}${voice.engine ? ` (${voice.engine})` : ''}`
}

function interpolatePath(pathPoints: number[][], t: number): { x: number; y: number } | null {
  if (pathPoints.length < 2) {
    return null
  }
  const normalized = Math.max(0, Math.min(0.99999, t))
  const segmentFloat = normalized * (pathPoints.length - 1)
  const segmentIdx = Math.floor(segmentFloat)
  const segmentT = segmentFloat - segmentIdx
  const start = pathPoints[segmentIdx]
  const end = pathPoints[Math.min(pathPoints.length - 1, segmentIdx + 1)]
  const x = start[0] + (end[0] - start[0]) * segmentT
  const y = start[1] + (end[1] - start[1]) * segmentT
  return { x, y }
}

function actorPathPosition(actor: SceneActor, playbackMs: number, fallbackX: number, fallbackY: number): { x: number; y: number } {
  if (!actor.motion || typeof actor.motion === 'string') {
    return { x: actor.x ?? fallbackX, y: actor.y ?? fallbackY }
  }
  const durationMs = Number(actor.motion.duration_ms || 4200)
  const pointsRaw = actor.motion.path_points
  const points = Array.isArray(pointsRaw)
    ? pointsRaw
        .filter((row): row is number[] => Array.isArray(row) && row.length >= 2)
        .map((row) => [Number(row[0]), Number(row[1])])
    : []
  const t = durationMs <= 0 ? 0 : (playbackMs % durationMs) / durationMs
  const mapped = interpolatePath(points, t)
  if (!mapped) {
    return { x: actor.x ?? fallbackX, y: actor.y ?? fallbackY }
  }
  return mapped
}

function chartProgress(chart: { at_ms?: number; duration_ms?: number } | undefined, playbackMs: number): number {
  if (!chart) {
    return 1
  }
  const start = Number(chart.at_ms || 0)
  const duration = Math.max(1, Number(chart.duration_ms || 1))
  const progress = (playbackMs - start) / duration
  return Math.max(0, Math.min(1, progress))
}

function progressivePolyline(points: number[][] | undefined, progress: number): number[][] {
  if (!points || points.length <= 1) {
    return points || []
  }
  const capped = Math.max(0, Math.min(1, progress))
  const required = Math.max(2, Math.ceil(capped * points.length))
  return points.slice(0, required)
}

function styleNumber(style: Record<string, unknown>, key: string, fallback: number): number {
  const raw = style[key]
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : fallback
}

function styleString(style: Record<string, unknown>, key: string, fallback: string): string {
  const raw = style[key]
  return typeof raw === 'string' && raw.trim() ? raw : fallback
}

function previewText(raw: string, max: number = 120): string {
  const clean = raw.trim()
  if (!clean) {
    return ''
  }
  return clean.length <= max ? clean : `${clean.slice(0, max)}...`
}

function normalizeAgentThreadText(raw: string): string {
  return raw.replace(/^OpenCommotion:\s*/i, '').trim()
}

export default function App() {
  const [prompt, setPrompt] = useState('show a moonwalk with adoption chart and pie')
  const [text, setText] = useState('')
  const [patches, setPatches] = useState<Patch[]>([])
  const [query, setQuery] = useState('')
  const [searchMode, setSearchMode] = useState<'lexical' | 'semantic' | 'hybrid'>('hybrid')
  const [results, setResults] = useState<ArtifactResult[]>([])
  const [running, setRunning] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [playbackMs, setPlaybackMs] = useState(0)
  const [durationMs, setDurationMs] = useState(0)
  const [voice, setVoice] = useState<VoicePayload | null>(null)
  const [qualityReport, setQualityReport] = useState<QualityReport | null>(null)
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [transcript, setTranscript] = useState('')
  const [transcribing, setTranscribing] = useState(false)
  const [lastError, setLastError] = useState('')
  const [runtimeCaps, setRuntimeCaps] = useState<RuntimeCapabilities | null>(null)
  const [capsLoading, setCapsLoading] = useState(false)
  const [capsError, setCapsError] = useState('')
  const [setupStep, setSetupStep] = useState(1)
  const [setupDraft, setSetupDraft] = useState<Record<string, string>>({})
  const [setupErrors, setSetupErrors] = useState<string[]>([])
  const [setupWarnings, setSetupWarnings] = useState<string[]>([])
  const [setupLoading, setSetupLoading] = useState(false)
  const [setupSaving, setSetupSaving] = useState(false)
  const [setupMessage, setSetupMessage] = useState('')
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [selectedRunId, setSelectedRunId] = useState('')
  const [queuedPrompt, setQueuedPrompt] = useState('autonomous turn: continue narrative and visuals')
  const [runActionLoading, setRunActionLoading] = useState(false)
  const [browserSpeaking, setBrowserSpeaking] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  const [agentLog, setAgentLog] = useState<AgentLogEntry[]>([])

  const session = useMemo(() => `sess-${Math.random().toString(36).slice(2)}`, [])
  const authHeaders = useMemo(() => {
    if (!gatewayApiKey) {
      return {}
    }
    return { 'x-api-key': gatewayApiKey }
  }, [])
  const lastTurnRef = useRef('')
  const setupMode = useMemo(() => {
    if (typeof window === 'undefined') {
      return false
    }
    const raw = new URLSearchParams(window.location.search).get('setup') || ''
    const value = raw.trim().toLowerCase()
    return value === '1' || value === 'true' || value === 'yes'
  }, [])
  const browserSpeechSupported = useMemo(
    () => typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window,
    [],
  )
  const appendAgentLog = useCallback((eventType: string, message: string) => {
    const line = message.trim()
    if (!line) {
      return
    }
    const at = new Date().toLocaleTimeString()
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    setAgentLog((current) => {
      const next = [...current, { id, at, event_type: eventType, message: line }]
      return next.length > 140 ? next.slice(next.length - 140) : next
    })
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined' || isTestMode) {
      return
    }
    const saved = window.localStorage.getItem('opencommotion.tools.open')
    if (saved === '1' || saved === '0') {
      setToolsOpen(saved === '1')
      return
    }
    if (setupMode) {
      setToolsOpen(true)
    }
  }, [setupMode, isTestMode])

  useEffect(() => {
    if (typeof window === 'undefined' || isTestMode) {
      return
    }
    window.localStorage.setItem('opencommotion.tools.open', toolsOpen ? '1' : '0')
  }, [toolsOpen, isTestMode])

  function speakInBrowser(textToSpeak: string): void {
    if (!browserSpeechSupported) {
      setLastError('Browser speech is not available in this browser. Configure a TTS engine in setup mode.')
      return
    }
    const cleanText = textToSpeak.trim()
    if (!cleanText) {
      return
    }
    try {
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(cleanText)
      utterance.onend = () => setBrowserSpeaking(false)
      utterance.onerror = () => {
        setBrowserSpeaking(false)
        setLastError('Browser speech failed. Try a different browser voice or configure backend TTS.')
      }
      setBrowserSpeaking(true)
      window.speechSynthesis.speak(utterance)
    } catch (err) {
      setBrowserSpeaking(false)
      const msg = formatClientError(err, 'browser speech', 'Browser speech failed')
      setLastError(msg)
    }
  }

  const refreshRuntimeCapabilities = useCallback(async () => {
    if (isTestMode) {
      return
    }
    setCapsLoading(true)
    setCapsError('')
    try {
      const res = await fetch(`${gateway}/v1/runtime/capabilities`, { headers: authHeaders })
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'runtime capabilities'))
      }
      const data = (await res.json()) as RuntimeCapabilities
      setRuntimeCaps(data)
    } catch (err) {
      const msg = formatClientError(err, 'runtime capabilities', 'Unknown capability failure')
      setCapsError(msg)
    } finally {
      setCapsLoading(false)
    }
  }, [authHeaders])

  const loadSetupState = useCallback(async () => {
    if (isTestMode) {
      return
    }
    setSetupLoading(true)
    try {
      const res = await fetch(`${gateway}/v1/setup/state`, { headers: authHeaders })
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'setup state'))
      }
      const data = (await res.json()) as SetupStateResponse
      setSetupDraft(data.state || {})
    } catch (err) {
      const msg = formatClientError(err, 'setup state', 'Unknown setup state failure')
      setLastError(msg)
    } finally {
      setSetupLoading(false)
    }
  }, [authHeaders])

  function updateSetupDraft(key: string, value: string): void {
    setSetupDraft((current) => ({ ...current, [key]: value }))
  }

  async function validateSetupDraft() {
    setSetupErrors([])
    setSetupWarnings([])
    setSetupMessage('')
    try {
      const res = await fetch(`${gateway}/v1/setup/validate`, {
        method: 'POST',
        headers: { ...authHeaders, 'content-type': 'application/json' },
        body: JSON.stringify({ values: setupDraft }),
      })
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'setup validate'))
      }
      const data = (await res.json()) as SetupValidateResponse
      setSetupErrors(data.errors || [])
      setSetupWarnings(data.warnings || [])
      if (data.ok) {
        setSetupMessage('Setup validation passed.')
      }
    } catch (err) {
      const msg = formatClientError(err, 'setup validate', 'Unknown setup validate failure')
      setLastError(msg)
    }
  }

  async function saveSetupDraft() {
    setSetupSaving(true)
    setSetupMessage('')
    try {
      const res = await fetch(`${gateway}/v1/setup/state`, {
        method: 'POST',
        headers: { ...authHeaders, 'content-type': 'application/json' },
        body: JSON.stringify({ values: setupDraft }),
      })
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'setup save'))
      }
      const data = (await res.json()) as {
        ok: boolean
        restart_required?: boolean
        applied_runtime?: boolean
        warnings?: string[]
      }
      setSetupWarnings(data.warnings || [])
      setSetupMessage(
        data.restart_required
          ? 'Setup saved. Automatic apply was partial; restart stack to apply all changes.'
          : 'Setup saved and applied.',
      )
      await refreshRuntimeCapabilities()
      await refreshRuns()
    } catch (err) {
      const msg = formatClientError(err, 'setup save', 'Unknown setup save failure')
      setLastError(msg)
    } finally {
      setSetupSaving(false)
    }
  }

  const refreshRuns = useCallback(async () => {
    if (isTestMode) {
      return
    }
    try {
      const res = await fetch(`${gateway}/v1/agent-runs`, { headers: authHeaders })
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'list runs'))
      }
      const data = (await res.json()) as { runs: AgentRun[] }
      const rows = data.runs || []
      setRuns(rows)
      if (!selectedRunId && rows.length) {
        setSelectedRunId(rows[0].run_id)
      }
    } catch (err) {
      const msg = formatClientError(err, 'list runs', 'Unknown list-runs failure')
      setLastError(msg)
    }
  }, [authHeaders, selectedRunId])

  async function createRun() {
    setRunActionLoading(true)
    try {
      const res = await fetch(`${gateway}/v1/agent-runs`, {
        method: 'POST',
        headers: { ...authHeaders, 'content-type': 'application/json' },
        body: JSON.stringify({ label: `run-${Date.now()}`, auto_run: true }),
      })
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'create run'))
      }
      const data = (await res.json()) as { run: AgentRun }
      if (data.run?.run_id) {
        setSelectedRunId(data.run.run_id)
      }
      await refreshRuns()
    } catch (err) {
      const msg = formatClientError(err, 'create run', 'Unknown create-run failure')
      setLastError(msg)
    } finally {
      setRunActionLoading(false)
    }
  }

  async function enqueueToRun() {
    if (!selectedRunId) {
      return
    }
    setRunActionLoading(true)
    try {
      const res = await fetch(`${gateway}/v1/agent-runs/${encodeURIComponent(selectedRunId)}/enqueue`, {
        method: 'POST',
        headers: { ...authHeaders, 'content-type': 'application/json' },
        body: JSON.stringify({ prompt: queuedPrompt }),
      })
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'enqueue'))
      }
      await refreshRuns()
    } catch (err) {
      const msg = formatClientError(err, 'enqueue', 'Unknown enqueue failure')
      setLastError(msg)
    } finally {
      setRunActionLoading(false)
    }
  }

  async function controlRun(action: 'run_once' | 'pause' | 'resume' | 'stop' | 'drain') {
    if (!selectedRunId) {
      return
    }
    setRunActionLoading(true)
    try {
      const res = await fetch(`${gateway}/v1/agent-runs/${encodeURIComponent(selectedRunId)}/control`, {
        method: 'POST',
        headers: { ...authHeaders, 'content-type': 'application/json' },
        body: JSON.stringify({ action }),
      })
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'run control'))
      }
      await refreshRuns()
    } catch (err) {
      const msg = formatClientError(err, 'run control', 'Unknown run-control failure')
      setLastError(msg)
    } finally {
      setRunActionLoading(false)
    }
  }

  function loadTurn(turn: TurnResult): void {
    if (!turn || turn.turn_id === lastTurnRef.current) {
      return
    }
    lastTurnRef.current = turn.turn_id
    setText(turn.text)
    setVoice(turn.voice)
    setQualityReport(turn.quality_report || null)
    const orderedPatches = [...(turn.visual_patches || [])].sort((a, b) => (a.at_ms || 0) - (b.at_ms || 0))
    setPatches(orderedPatches)
    const totalDuration = calcDurationMs(turn)
    setDurationMs(totalDuration)
    setPlaybackMs(0)
    setPlaying(true)
    const normalizedText = normalizeAgentThreadText(turn.text || '')
    appendAgentLog(
      'agent.turn.completed',
      `Turn ${turn.turn_id} completed. ${turn.visual_patches.length} patches. Agent said: ${previewText(normalizedText, 140)}`,
    )
    if (turn.voice?.engine === 'tone-fallback') {
      speakInBrowser(turn.text || '')
    }
  }

  function formatClientError(err: unknown, op: string, fallback: string): string {
    if (err instanceof Error) {
      const message = err.message?.trim() || ''
      if (message) {
        if (/failed to fetch|networkerror|load failed/i.test(message)) {
          return (
            `${op} failed: could not reach ${gateway}. ` +
            `Check service status with opencommotion -status, then open ${gateway}/health.`
          )
        }
        if (/aborted|timeout/i.test(message)) {
          return `${op} failed: request timed out or was aborted. ${message}`
        }
        return message
      }
    }
    return fallback
  }

  async function fetchWithTimeout(input: string, init: RequestInit, timeoutMs: number): Promise<Response> {
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), timeoutMs)
    try {
      return await fetch(input, { ...init, signal: controller.signal })
    } finally {
      window.clearTimeout(timer)
    }
  }

  async function buildApiErrorMessage(res: Response, op: string): Promise<string> {
    let details = ''
    try {
      const rawText = (await res.text()).trim()
      if (rawText) {
        try {
          const body = JSON.parse(rawText) as Record<string, unknown>
          const raw = (body.detail ?? body) as unknown
          if (typeof raw === 'string') {
            details = raw
          } else if (Array.isArray(raw)) {
            const messages = raw
              .map((item) => {
                if (typeof item === 'string') {
                  return item
                }
                if (item && typeof item === 'object') {
                  const row = item as Record<string, unknown>
                  if (typeof row.msg === 'string') {
                    return row.msg
                  }
                  return JSON.stringify(row)
                }
                return ''
              })
              .filter(Boolean)
            details = messages.join(' | ')
          } else if (raw && typeof raw === 'object') {
            const detailObj = raw as Record<string, unknown>
            const err = typeof detailObj.error === 'string' ? detailObj.error : ''
            const provider = typeof detailObj.provider === 'string' ? detailObj.provider : ''
            const engine = typeof detailObj.engine === 'string' ? detailObj.engine : ''
            const message = typeof detailObj.message === 'string' ? detailObj.message : ''
            const parts = [err, provider || engine, message].filter(Boolean)
            details = parts.join(' | ')
            if (!details) {
              details = JSON.stringify(detailObj)
            }
          }
        } catch {
          details = rawText
        }
      }
    } catch {
      // no-op: fallback to status-only error below
    }
    return details ? `${op} failed (${res.status}): ${details}` : `${op} failed (${res.status})`
  }

  async function runTurn() {
    setRunning(true)
    setLastError('')
    appendAgentLog('agent.turn.requested', `Prompt: ${previewText(prompt, 160)}`)
    try {
      const res = await fetchWithTimeout(`${gateway}/v1/orchestrate`, {
        method: 'POST',
        headers: { ...authHeaders, 'content-type': 'application/json' },
        body: JSON.stringify({ session_id: session, prompt }),
      }, 45000)
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'orchestrate'))
      }
      const data = (await res.json()) as TurnResult
      loadTurn(data)
    } catch (err) {
      const msg = formatClientError(err, 'orchestrate', 'Unknown run-turn failure')
      setLastError(msg)
      appendAgentLog('agent.turn.failed', msg)
    } finally {
      setRunning(false)
    }
  }

  async function transcribeSelectedAudio() {
    if (!audioFile) {
      return
    }
    setTranscribing(true)
    setLastError('')
    try {
      const body = new FormData()
      body.append('audio', audioFile)

      const res = await fetch(`${gateway}/v1/voice/transcribe`, {
        method: 'POST',
        headers: authHeaders,
        body,
      })
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'transcribe'))
      }
      const data = (await res.json()) as { transcript: { final: string } }
      const finalText = data.transcript.final || ''
      setTranscript(finalText)
      if (finalText) {
        setPrompt(finalText)
      }
    } catch (err) {
      const msg = formatClientError(err, 'transcribe', 'Unknown transcription failure')
      setLastError(msg)
    } finally {
      setTranscribing(false)
    }
  }

  async function saveArtifact() {
    setLastError('')
    try {
      const res = await fetch(`${gateway}/v1/artifacts/save`, {
        method: 'POST',
        headers: { ...authHeaders, 'content-type': 'application/json' },
        body: JSON.stringify({
          title: `Turn ${new Date().toLocaleTimeString()}`,
          summary: text,
          tags: ['favorite', 'manual'],
          saved_by: 'ui',
        }),
      })
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'save'))
      }
    } catch (err) {
      const msg = formatClientError(err, 'save artifact', 'Unknown save failure')
      setLastError(msg)
    }
  }

  async function searchArtifacts() {
    setLastError('')
    try {
      const res = await fetch(
        `${gateway}/v1/artifacts/search?q=${encodeURIComponent(query)}&mode=${encodeURIComponent(searchMode)}`,
        { headers: authHeaders },
      )
      if (!res.ok) {
        throw new Error(await buildApiErrorMessage(res, 'search'))
      }
      const data = (await res.json()) as { results: ArtifactResult[] }
      setResults(data.results)
    } catch (err) {
      const msg = formatClientError(err, 'search artifacts', 'Unknown search failure')
      setLastError(msg)
    }
  }

  useEffect(() => {
    if (!playing) {
      return
    }

    const timer = window.setInterval(() => {
      setPlaybackMs((current) => {
        const next = Math.min(durationMs, current + 50)
        if (next >= durationMs) {
          setPlaying(false)
        }
        return next
      })
    }, 50)

    return () => {
      window.clearInterval(timer)
    }
  }, [playing, durationMs])

  useEffect(() => {
    if (isTestMode || typeof WebSocket === 'undefined') {
      return
    }

    let closedByClient = false
    const ws = new WebSocket(
      gatewayApiKey ? `${wsGateway}/v1/events/ws?api_key=${encodeURIComponent(gatewayApiKey)}` : `${wsGateway}/v1/events/ws`,
    )
    const heartbeat = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 10000)

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as {
          event_type?: string
          payload?: unknown
          session_id?: string
          turn_id?: string
        }
        if (parsed.event_type === 'agent.run.state') {
          const payload = parsed.payload as { state?: { status?: string; run_id?: string; queue?: { queued?: number } } } | undefined
          const state = payload?.state
          const status = state?.status || 'unknown'
          const runId = state?.run_id || parsed.session_id || 'n/a'
          const queued = Number(state?.queue?.queued || 0)
          appendAgentLog('agent.run.state', `run=${runId} status=${status} queue=${queued}`)
          void refreshRuns()
          return
        }
        if (parsed.event_type === 'agent.turn.failed') {
          const payload = parsed.payload as { error?: string } | undefined
          const message = payload?.error?.trim()
          setLastError(message ? `agent.turn.failed: ${message}` : 'Agent run turn failed. Check run status for details.')
          appendAgentLog('agent.turn.failed', message || 'Agent run turn failed.')
          void refreshRuns()
          return
        }
        if (parsed.event_type !== 'gateway.event') {
          if (parsed.event_type) {
            appendAgentLog(parsed.event_type, 'Received backend event.')
          }
          return
        }
        const payload = parsed.payload as TurnResult | undefined
        if (!payload) {
          return
        }
        if (payload.session_id !== session) {
          const normalizedText = normalizeAgentThreadText(payload.text || '')
          appendAgentLog(
            'gateway.event',
            `session=${payload.session_id} turn=${payload.turn_id} text=${previewText(normalizedText, 90) || '[no text]'}`,
          )
          return
        }
        loadTurn(payload)
      } catch {
        // Ignore malformed ws events.
      }
    }

    ws.onerror = () => {
      setLastError(
        `event stream error: could not reach ${wsGateway}/v1/events/ws. Check scripts/opencommotion.py -status.`,
      )
      appendAgentLog('event.stream.error', `Could not reach ${wsGateway}/v1/events/ws`)
    }

    ws.onclose = (event) => {
      if (closedByClient) {
        return
      }
      if (event.code !== 1000) {
        setLastError(
          `event stream closed (${event.code}). Check scripts/opencommotion.py -status and reload the page.`,
        )
        appendAgentLog('event.stream.closed', `Socket closed with code ${event.code}`)
      }
    }

    return () => {
      closedByClient = true
      window.clearInterval(heartbeat)
      ws.close()
    }
  }, [session, authHeaders, refreshRuns, appendAgentLog])

  useEffect(() => {
    return () => {
      if (browserSpeechSupported) {
        window.speechSynthesis.cancel()
      }
    }
  }, [browserSpeechSupported])

  useEffect(() => {
    if (typeof window === 'undefined' || !toolsOpen) {
      return
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setToolsOpen(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [toolsOpen])

  useEffect(() => {
    if (isTestMode) {
      return
    }
    if (setupMode) {
      refreshRuntimeCapabilities()
      loadSetupState()
    }
    refreshRuns()
    const timer = window.setInterval(() => {
      if (setupMode) {
        refreshRuntimeCapabilities()
      }
    }, 12000)
    const runTimer = window.setInterval(() => {
      refreshRuns()
    }, 6000)
    return () => {
      window.clearInterval(timer)
      window.clearInterval(runTimer)
    }
  }, [refreshRuntimeCapabilities, loadSetupState, refreshRuns, setupMode])

  const scene = useMemo(() => buildScene(patches, playbackMs), [patches, playbackMs])
  const appliedCount = useMemo(
    () => patches.filter((patch) => (patch.at_ms || 0) <= playbackMs).length,
    [patches, playbackMs],
  )

  const actorEntries = Object.entries(scene.actors).sort(([, leftActor], [, rightActor]) => {
    const leftStyle = (leftActor.style || {}) as Record<string, unknown>
    const rightStyle = (rightActor.style || {}) as Record<string, unknown>
    return styleNumber(leftStyle, 'z', 0) - styleNumber(rightStyle, 'z', 0)
  })
  const lineChart = scene.charts.adoption_curve as { points?: number[][]; at_ms?: number; duration_ms?: number } | undefined
  const pieChart = scene.charts.saturation_pie as
    | { slices?: Array<{ label: string; value: number }>; at_ms?: number; duration_ms?: number }
    | undefined
  const segmentedAttach = scene.charts.segmented_attach as
    | { segments?: Array<{ label: string; target: number; color?: string }>; at_ms?: number; duration_ms?: number }
    | undefined
  const lineProgress = chartProgress(lineChart, playbackMs)
  const linePoints = progressivePolyline(lineChart?.points, lineProgress)
  const pieProgress = chartProgress(pieChart, playbackMs)
  const pieSlices = (pieChart?.slices || []).map((slice, idx) => ({
    ...slice,
    value: idx === 0 ? Math.round(slice.value * pieProgress) : slice.value,
  }))
  const segmentedProgress = chartProgress(segmentedAttach, playbackMs)
  const segmentedValues = (segmentedAttach?.segments || []).map((segment) => ({
    ...segment,
    current: Math.round(Number(segment.target || 0) * segmentedProgress),
  }))
  const renderMode = scene.render.mode || '2d'
  const mood = (scene.environment.mood || {}) as Record<string, unknown>
  const bubbleFx = scene.fx.bubble_emitter as { particles?: Array<Record<string, number>> } | undefined
  const bounceFx = scene.fx.bouncing_ball as { start_ms?: number; step_ms?: number; words_count?: number } | undefined
  const causticFx = scene.fx.caustic_pattern as { intensity?: number; phase?: number } | undefined
  const waterFx = scene.fx.water_shimmer as { speed?: number; surface_amp?: number } | undefined
  const lyricsWords = scene.lyrics.words || []
  const audioUri = voice?.segments?.[0]?.audio_uri
  const toneFallback = voice?.engine === 'tone-fallback'
  const llmProvider = runtimeCaps?.llm?.selected_provider || 'unknown'
  const llmEffectiveProvider = runtimeCaps?.llm?.effective_provider || llmProvider
  const llmReady = runtimeCaps?.llm?.effective_ready === true
  const sttEngine = runtimeCaps?.voice?.stt?.selected_engine || 'unknown'
  const ttsEngine = runtimeCaps?.voice?.tts?.selected_engine || 'unknown'
  const selectedRun = runs.find((run) => run.run_id === selectedRunId) || null

  return (
    <div className="app-shell">
      <header className="brand-bar card">
        <div>
          <p className="eyebrow">OpenCommotion Studio</p>
          <h1>OpenCommotion</h1>
          <p className="lead">Prompt in. Narrated motion scene out. No interpretive dance required.</p>
        </div>
        <div className="brand-right">
          <div className="brand-badges">
            <span className={`badge ${llmReady ? 'ok' : 'warn'}`}>LLM: {llmEffectiveProvider}</span>
            <span className="badge">STT: {sttEngine}</span>
            <span className="badge">TTS: {ttsEngine}</span>
            <span className="badge">UI: v{uiVersion}</span>
          </div>
          <button className="tools-toggle" onClick={() => setToolsOpen((current) => !current)}>
            {toolsOpen ? 'Close Tools' : 'Tools'}
          </button>
        </div>
      </header>

      <main className="studio-main">
        <section className="card visual-stage-card" data-testid="visual-stage-card">
          <div className="row controls">
            <h2>Visual Surface</h2>
            <button onClick={() => setPlaying((v) => !v)} disabled={!patches.length}>
              {playing ? 'Pause' : 'Play'}
            </button>
            <button
              onClick={() => {
                setPlaybackMs(0)
                setPlaying(true)
              }}
              disabled={!patches.length}
            >
              Replay
            </button>
          </div>

          {qualityReport ? (
            <p className={qualityReport.ok ? 'muted' : 'error'}>
              Graph quality: {qualityReport.ok ? 'compatible' : 'needs correction'}
              {qualityReport.failures?.length ? ` (${qualityReport.failures.join(', ')})` : ''}
            </p>
          ) : null}

          <svg className="visual-canvas" viewBox="0 0 720 360" aria-label="visual stage">
            <defs>
              <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor={mood.phase === 'night' ? '#020617' : mood.phase === 'day-to-dusk' ? '#1e293b' : '#111827'} />
                <stop offset="100%" stopColor={mood.phase === 'night' ? '#1d4ed8' : mood.phase === 'day-to-dusk' ? '#f59e0b' : '#0ea5e9'} />
              </linearGradient>
            </defs>
            <rect x="0" y="0" width="720" height="360" fill="url(#bg)" rx="14" />

            {renderMode === '3d' ? <text x="24" y="104" fill="#f8fafc" fontSize="13">Render mode: 3D</text> : null}
            {renderMode === '2d' ? <text x="24" y="104" fill="#f8fafc" fontSize="13">Render mode: 2D</text> : null}

            <rect x="420" y="206" width="240" height="120" fill="rgba(2,6,23,0.58)" rx="12" />
            {linePoints.length >= 2 ? (
              <polyline
                points={mapPolyline(linePoints, 440, 220, 180, 80)}
                fill="none"
                stroke="#22d3ee"
                strokeWidth="4"
              />
            ) : null}

            {pieSlices.length ? (
              <g>
                <circle cx="615" cy="138" r="45" fill="#334155" />
                <text x="615" y="143" textAnchor="middle" fill="#e2e8f0" fontSize="13">
                  {pieSlices[0]?.label}: {pieSlices[0]?.value}%
                </text>
              </g>
            ) : null}

            {segmentedValues.length ? (
              <g>
                <rect x="430" y="46" width="248" height="140" fill="#020617aa" rx="12" />
                {segmentedValues.map((segment, idx) => {
                  const barBaseY = 168
                  const barHeight = Math.round((segment.current / 100) * 84)
                  const x = 446 + idx * 76
                  const y = barBaseY - barHeight
                  return (
                    <g key={`seg-${segment.label}`}>
                      <rect x={x} y={y} width="42" height={barHeight} fill={segment.color || '#22d3ee'} rx="6" />
                      <text x={x + 21} y={barBaseY + 15} textAnchor="middle" fill="#cbd5e1" fontSize="10">
                        {segment.label}
                      </text>
                      <text x={x + 21} y={y - 4} textAnchor="middle" fill="#e2e8f0" fontSize="10">
                        {segment.current}%
                      </text>
                    </g>
                  )
                })}
              </g>
            ) : null}

            {causticFx ? (
              <g opacity={Math.max(0.15, Math.min(0.6, Number(causticFx.intensity || 0.32)))}>
                <path d="M210 272 C260 228, 338 308, 390 258" stroke="#fde68a" strokeWidth="4" fill="none" />
                <path d="M240 292 C302 244, 362 316, 426 268" stroke="#fef9c3" strokeWidth="3" fill="none" />
              </g>
            ) : null}

            {waterFx ? (
              <path
                d={`M250 154 C292 ${150 + Math.sin(playbackMs / 380) * 5}, 362 ${159 + Math.cos(playbackMs / 430) * 6}, 404 153`}
                stroke="#93c5fd"
                strokeWidth="2"
                fill="none"
                opacity={0.75}
              />
            ) : null}

            {actorEntries.map(([id, actor]) => {
              const x = actor.x ?? 140
              const y = actor.y ?? 170
              const actorStyle = (actor.style || {}) as Record<string, unknown>

              if (actor.type === 'character') {
                return (
                  <g key={id}>
                    <circle cx={x} cy={y - 18} r="18" fill="#f59e0b" />
                    <rect x={x - 16} y={y} width="32" height="54" fill="#fef3c7" rx="8" />
                    {actor.animation?.name === 'moonwalk' ? (
                      <text x={x - 30} y={y + 74} fill="#fde68a" fontSize="11">moonwalk</text>
                    ) : null}
                  </g>
                )
              }

              if (actor.type === 'globe') {
                return <circle key={id} cx={x} cy={y} r="36" fill="#3b82f6" />
              }

              if (actor.type === 'ufo') {
                return (
                  <g key={id}>
                    <ellipse cx={x || 470} cy={y || 95} rx="30" ry="12" fill="#cbd5e1" />
                    <ellipse cx={x || 470} cy={(y || 95) - 4} rx="12" ry="8" fill="#93c5fd" />
                    {describeMotion(actor).includes('landing') ? (
                      <path d={`M${(x || 470) - 10},${(y || 95) + 12} L${x || 470},${(y || 95) + 55} L${(x || 470) + 10},${(y || 95) + 12}`} fill="#fef08a66" />
                    ) : null}
                  </g>
                )
              }

              if (actor.type === 'bowl') {
                const bowlShape = styleString(actorStyle, 'shape', 'round')
                if (bowlShape === 'square') {
                  return (
                    <g key={id}>
                      <rect x={x - 92} y={y - 82} width="184" height="164" rx="18" fill={renderMode === '3d' ? '#dbeafe66' : '#bfdbfe44'} />
                      <rect x={x - 92} y={y - 82} width="184" height="164" rx="18" fill="none" stroke="#e0f2fe" strokeWidth="5" />
                      <rect x={x - 72} y={y - 66} width="144" height="14" rx="6" fill="#93c5fd55" />
                      <ellipse cx={x} cy={y + 92} rx="110" ry="18" fill="#0f172a55" />
                    </g>
                  )
                }
                return (
                  <g key={id}>
                    <ellipse cx={x} cy={y + 46} rx="118" ry="18" fill="#0f172a55" />
                    <ellipse cx={x} cy={y} rx="94" ry="86" fill={renderMode === '3d' ? '#dbeafe66' : '#bfdbfe44'} />
                    <ellipse cx={x} cy={y - 1} rx="94" ry="86" fill="none" stroke="#e0f2fe" strokeWidth="5" />
                    <ellipse cx={x} cy={y - 54} rx="66" ry="13" fill="#93c5fd55" />
                  </g>
                )
              }

              if (actor.type === 'fish') {
                const pos = actorPathPosition(actor, playbackMs, 310, 205)
                const fishFill = styleString(actorStyle, 'fill', '#f59e0b')
                const fishTail = styleString(actorStyle, 'tail', fishFill)
                return (
                  <g key={id}>
                    <ellipse cx={pos.x} cy={pos.y} rx="24" ry="13" fill={fishFill} />
                    <polygon points={`${pos.x - 23},${pos.y} ${pos.x - 41},${pos.y - 11} ${pos.x - 41},${pos.y + 11}`} fill={fishTail} />
                    <circle cx={pos.x + 11} cy={pos.y - 3} r="2.4" fill="#111827" />
                  </g>
                )
              }

              if (actor.type === 'cow') {
                const pos = actorPathPosition(actor, playbackMs, x, y)
                return (
                  <g key={id}>
                    <rect x={pos.x - 34} y={pos.y - 20} width="68" height="38" fill="#f8fafc" rx="10" />
                    <circle cx={pos.x + 25} cy={pos.y - 14} r="12" fill="#f8fafc" />
                    <circle cx={pos.x + 18} cy={pos.y - 14} r="2" fill="#111827" />
                    <circle cx={pos.x + 28} cy={pos.y - 14} r="2" fill="#111827" />
                    <rect x={pos.x - 30} y={pos.y + 15} width="8" height="18" fill="#f8fafc" rx="2" />
                    <rect x={pos.x - 10} y={pos.y + 15} width="8" height="18" fill="#f8fafc" rx="2" />
                    <rect x={pos.x + 10} y={pos.y + 15} width="8" height="18" fill="#f8fafc" rx="2" />
                    <rect x={pos.x + 26} y={pos.y + 15} width="8" height="18" fill="#f8fafc" rx="2" />
                  </g>
                )
              }

              if (actor.type === 'moon') {
                return (
                  <g key={id}>
                    <circle cx={x} cy={y} r="34" fill="#fef3c7" />
                    <circle cx={x + 10} cy={y - 8} r="6" fill="#fde68a" />
                    <circle cx={x - 12} cy={y + 10} r="5" fill="#fde68a" />
                  </g>
                )
              }

              if (actor.type === 'plant') {
                const sway = actor.animation?.name === 'sway' ? Math.sin(playbackMs / 420) * 7 : 0
                return (
                  <g key={id}>
                    <path d={`M${x},${y} C${x - 10 + sway},${y - 38} ${x + 16 + sway},${y - 74} ${x + 2 + sway},${y - 116}`} stroke="#4ade80" strokeWidth="4" fill="none" />
                    <path d={`M${x + 4},${y - 8} C${x + 10 + sway},${y - 42} ${x - 8 + sway},${y - 76} ${x + 10 + sway},${y - 110}`} stroke="#22c55e" strokeWidth="3" fill="none" />
                  </g>
                )
              }

              if (actor.type === 'box' || actor.type === 'square' || actor.type === 'rectangle') {
                const pos = actorPathPosition(actor, playbackMs, x, y)
                const width = styleNumber(actorStyle, 'width', actor.type === 'rectangle' ? 140 : 96)
                const height = styleNumber(actorStyle, 'height', actor.type === 'rectangle' ? 84 : width)
                const fill = styleString(actorStyle, 'fill', '#22d3ee')
                const stroke = styleString(actorStyle, 'stroke', '#e2e8f0')
                const lineWidth = styleNumber(actorStyle, 'line_width', 4)
                return (
                  <rect
                    key={id}
                    x={pos.x - width / 2}
                    y={pos.y - height / 2}
                    width={width}
                    height={height}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={lineWidth}
                    rx={actor.type === 'square' ? 8 : 10}
                  />
                )
              }

              if (actor.type === 'circle' || actor.type === 'dot') {
                const pos = actorPathPosition(actor, playbackMs, x, y)
                const fill = styleString(actorStyle, 'fill', '#22d3ee')
                const stroke = styleString(actorStyle, 'stroke', '#e2e8f0')
                const lineWidth = styleNumber(actorStyle, 'line_width', 3)
                const radius = styleNumber(actorStyle, 'radius', actor.type === 'dot' ? 8 : 44)
                return <circle key={id} cx={pos.x} cy={pos.y} r={radius} fill={fill} stroke={stroke} strokeWidth={lineWidth} />
              }

              if (actor.type === 'line') {
                const pos = actorPathPosition(actor, playbackMs, x, y)
                const dx = pos.x - x
                const dy = pos.y - y
                const x2 = styleNumber(actorStyle, 'x2', x + 180)
                const y2 = styleNumber(actorStyle, 'y2', y)
                const stroke = styleString(actorStyle, 'stroke', '#22d3ee')
                const lineWidth = styleNumber(actorStyle, 'line_width', 4)
                return <line key={id} x1={x + dx} y1={y + dy} x2={x2 + dx} y2={y2 + dy} stroke={stroke} strokeWidth={lineWidth} />
              }

              if (actor.type === 'triangle') {
                const pos = actorPathPosition(actor, playbackMs, x, y)
                const size = styleNumber(actorStyle, 'size', 100)
                const fill = styleString(actorStyle, 'fill', '#22d3ee')
                const stroke = styleString(actorStyle, 'stroke', '#e2e8f0')
                const lineWidth = styleNumber(actorStyle, 'line_width', 4)
                const p1 = `${pos.x},${pos.y - size / 2}`
                const p2 = `${pos.x - size / 2},${pos.y + size / 2}`
                const p3 = `${pos.x + size / 2},${pos.y + size / 2}`
                return <polygon key={id} points={`${p1} ${p2} ${p3}`} fill={fill} stroke={stroke} strokeWidth={lineWidth} />
              }

              if (actor.type === 'polyline') {
                const pos = actorPathPosition(actor, playbackMs, x, y)
                const dx = pos.x - x
                const dy = pos.y - y
                const stroke = styleString(actorStyle, 'stroke', '#22d3ee')
                const lineWidth = styleNumber(actorStyle, 'line_width', 4)
                const points = parseStylePoints(actorStyle)
                if (points.length < 2) {
                  return null
                }
                const polylinePoints = points.map((row) => `${row[0] + dx},${row[1] + dy}`).join(' ')
                return <polyline key={id} points={polylinePoints} fill="none" stroke={stroke} strokeWidth={lineWidth} />
              }

              if (actor.type === 'polygon') {
                const pos = actorPathPosition(actor, playbackMs, x, y)
                const dx = pos.x - x
                const dy = pos.y - y
                const fill = styleString(actorStyle, 'fill', '#22d3ee')
                const stroke = styleString(actorStyle, 'stroke', '#e2e8f0')
                const lineWidth = styleNumber(actorStyle, 'line_width', 2)
                const points = parseStylePoints(actorStyle)
                if (points.length < 3) {
                  return null
                }
                const polygonPoints = points.map((row) => `${row[0] + dx},${row[1] + dy}`).join(' ')
                return <polygon key={id} points={polygonPoints} fill={fill} stroke={stroke} strokeWidth={lineWidth} />
              }

              return null
            })}

            {(bubbleFx?.particles || []).slice(0, 28).map((particle, idx) => {
              const startX = Number(particle.x || 0.5)
              const startY = Number(particle.start_y || 0.84)
              const size = Number(particle.size || 3.5)
              const rise = Number(particle.rise_per_s || 0.08)
              const drift = Number(particle.drift || 0)
              const phase = Number(particle.phase || 0)
              const timeS = playbackMs / 1000
              const yNorm = startY - ((timeS * rise + phase) % 0.85)
              const xNorm = startX + Math.sin((timeS + phase) * 2.4) * drift
              const cx = 230 + xNorm * 210
              const cy = 120 + yNorm * 170
              return <circle key={`bubble-${idx}`} cx={cx} cy={cy} r={size * 0.55} fill="#dbeafe99" stroke="#ffffff88" strokeWidth="0.7" />
            })}

            {lyricsWords.length ? (
              <g>
                {lyricsWords.map((word, idx) => {
                  const x = 80 + idx * 88
                  return (
                    <text key={`lyric-${idx}`} x={x} y={338} textAnchor="middle" fill="#f8fafc" fontSize="20">
                      {word.text}
                    </text>
                  )
                })}
                {bounceFx ? (() => {
                  const startMs = Number(bounceFx.start_ms || scene.lyrics.start_ms || 0)
                  const stepMs = Math.max(120, Number(bounceFx.step_ms || scene.lyrics.step_ms || 420))
                  const idx = Math.max(
                    0,
                    Math.min(lyricsWords.length - 1, Math.floor((playbackMs - startMs) / stepMs)),
                  )
                  const ballX = 80 + idx * 88
                  const bob = 8 + Math.abs(Math.sin(playbackMs / 160)) * 10
                  return <circle cx={ballX} cy={328 - bob} r="8" fill="#f43f5e" />
                })() : null}
              </g>
            ) : null}

            <text x="24" y="32" fill="#e2e8f0" fontSize="20">Patch count: {patches.length}</text>
            <text x="24" y="56" fill="#cbd5e1" fontSize="14">Applied: {appliedCount}</text>
            <text x="24" y="80" fill="#cbd5e1" fontSize="14">Playback: {Math.round(playbackMs)}ms / {durationMs}ms</text>

            {scene.annotations.slice(-2).map((a, idx) => (
              <text key={`${a.text}-${idx}`} x="24" y={324 - idx * 20} fill="#f8fafc" fontSize="13">{a.text}</text>
            ))}
          </svg>
        </section>

        <section className="card prompt-composer" data-testid="prompt-composer">
          <h2>Prompt Composer</h2>
          <p className="muted">Session: {session}</p>
          <textarea
            aria-label="prompt input"
            className="composer-input"
            rows={4}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <div className="row">
            <button onClick={runTurn} disabled={running}>{running ? 'Running...' : 'Run Turn'}</button>
            <button onClick={saveArtifact} disabled={!text}>Save</button>
            <button onClick={() => setToolsOpen((current) => !current)}>{toolsOpen ? 'Hide Tools' : 'Open Tools'}</button>
          </div>
          {lastError ? <p className="error">{lastError}</p> : null}
        </section>

        <section className="card agent-log-panel" data-testid="agent-log-panel">
          <div className="row controls">
            <h2>Backend Agent Thread</h2>
            <button onClick={() => setAgentLog([])} disabled={!agentLog.length}>Clear</button>
          </div>
          <p className="muted">Live event stream: what the backend agent says and what it is doing.</p>
          <div className="agent-log-window" role="log" aria-live="polite">
            {agentLog.length ? (
              [...agentLog].reverse().map((entry) => (
                <p className="agent-log-row" key={entry.id}>
                  <span className="agent-log-time">[{entry.at}]</span>
                  <span className="agent-log-event">{entry.event_type}</span>
                  <span className="agent-log-message">{entry.message}</span>
                </p>
              ))
            ) : (
              <p className="muted">No backend events yet.</p>
            )}
          </div>
        </section>
      </main>

      <div
        className={`tools-overlay ${toolsOpen ? 'open' : ''}`}
        onClick={() => setToolsOpen(false)}
        aria-hidden={toolsOpen ? 'false' : 'true'}
      />

      <aside className={`tools-drawer panel ${toolsOpen ? 'open' : ''}`} aria-label="tools drawer">
        <div className="drawer-header">
          <h2>Tools</h2>
          <button onClick={() => setToolsOpen(false)}>Close</button>
        </div>

        <div className="control-panel">
          {setupMode ? (
            <section className="setup-panel">
              <h3>Setup Status</h3>
              <p className="muted">LLM provider: {llmProvider}</p>
              <p className="muted">Active route: {llmEffectiveProvider}</p>
              <p className="muted">LLM ready: {llmReady ? 'yes' : 'needs config'}</p>
              <p className="muted">STT engine: {sttEngine}</p>
              <p className="muted">TTS engine: {ttsEngine}</p>
              {runtimeCaps?.llm?.message ? <p className="error">{runtimeCaps.llm.message}</p> : null}
              {capsError ? <p className="error">{capsError}</p> : null}
              <div className="row">
                <button onClick={refreshRuntimeCapabilities} disabled={capsLoading}>
                  {capsLoading ? 'Refreshing...' : 'Refresh Setup'}
                </button>
                <button onClick={loadSetupState} disabled={setupLoading}>
                  {setupLoading ? 'Loading...' : 'Load Wizard'}
                </button>
              </div>
              <p className="muted">Setup Wizard step {setupStep}/3</p>
              <div className="row">
                <button onClick={() => setSetupStep((current) => Math.max(1, current - 1))} disabled={setupStep <= 1}>
                  Previous
                </button>
                <button onClick={() => setSetupStep((current) => Math.min(3, current + 1))} disabled={setupStep >= 3}>
                  Next
                </button>
              </div>
              {setupStep === 1 ? (
                <div>
                  <label className="muted">LLM provider</label>
                  <select
                    value={setupDraft.OPENCOMMOTION_LLM_PROVIDER || 'ollama'}
                    onChange={(e) => updateSetupDraft('OPENCOMMOTION_LLM_PROVIDER', e.target.value)}
                  >
                    <option value="ollama">ollama</option>
                    <option value="openai-compatible">openai-compatible</option>
                    <option value="codex-cli">codex-cli</option>
                    <option value="openclaw-cli">openclaw-cli</option>
                    <option value="openclaw-openai">openclaw-openai</option>
                    <option value="heuristic">heuristic</option>
                  </select>
                  <label className="muted">Model</label>
                  <input
                    value={setupDraft.OPENCOMMOTION_LLM_MODEL || ''}
                    onChange={(e) => updateSetupDraft('OPENCOMMOTION_LLM_MODEL', e.target.value)}
                    placeholder="provider model"
                  />
                </div>
              ) : null}
              {setupStep === 2 ? (
                <div>
                  <label className="muted">STT engine</label>
                  <select
                    value={setupDraft.OPENCOMMOTION_STT_ENGINE || 'auto'}
                    onChange={(e) => updateSetupDraft('OPENCOMMOTION_STT_ENGINE', e.target.value)}
                  >
                    <option value="auto">auto</option>
                    <option value="faster-whisper">faster-whisper</option>
                    <option value="vosk">vosk</option>
                    <option value="openai-compatible">openai-compatible</option>
                    <option value="text-fallback">text-fallback</option>
                  </select>
                  <label className="muted">TTS engine</label>
                  <select
                    value={setupDraft.OPENCOMMOTION_TTS_ENGINE || 'auto'}
                    onChange={(e) => updateSetupDraft('OPENCOMMOTION_TTS_ENGINE', e.target.value)}
                  >
                    <option value="auto">auto</option>
                    <option value="piper">piper</option>
                    <option value="espeak">espeak</option>
                    <option value="openai-compatible">openai-compatible</option>
                    <option value="tone-fallback">tone-fallback</option>
                  </select>
                  <label className="muted">Strict real engines</label>
                  <select
                    value={setupDraft.OPENCOMMOTION_VOICE_REQUIRE_REAL_ENGINES || 'false'}
                    onChange={(e) => updateSetupDraft('OPENCOMMOTION_VOICE_REQUIRE_REAL_ENGINES', e.target.value)}
                  >
                    <option value="false">false</option>
                    <option value="true">true</option>
                  </select>
                </div>
              ) : null}
              {setupStep === 3 ? (
                <div>
                  <label className="muted">Auth mode</label>
                  <select
                    value={setupDraft.OPENCOMMOTION_AUTH_MODE || 'api-key'}
                    onChange={(e) => updateSetupDraft('OPENCOMMOTION_AUTH_MODE', e.target.value)}
                  >
                    <option value="api-key">api-key</option>
                    <option value="network-trust">network-trust</option>
                  </select>
                  <p className="muted">
                    network-trust default allow list is local machine only: 127.0.0.1/32,::1/128
                  </p>
                  <label className="muted">API keys (comma-separated)</label>
                  <input
                    value={setupDraft.OPENCOMMOTION_API_KEYS || ''}
                    onChange={(e) => updateSetupDraft('OPENCOMMOTION_API_KEYS', e.target.value)}
                    placeholder="dev-opencommotion-key"
                  />
                  <label className="muted">Allowed IP/CIDR list (network-trust mode)</label>
                  <input
                    value={setupDraft.OPENCOMMOTION_ALLOWED_IPS || ''}
                    onChange={(e) => updateSetupDraft('OPENCOMMOTION_ALLOWED_IPS', e.target.value)}
                    placeholder="127.0.0.1/32,::1/128 (local-machine-only default)"
                  />
                </div>
              ) : null}
              <div className="row">
                <button onClick={validateSetupDraft}>Validate Setup</button>
                <button onClick={saveSetupDraft} disabled={setupSaving}>
                  {setupSaving ? 'Saving...' : 'Save Setup'}
                </button>
              </div>
              {setupMessage ? <p className="muted">{setupMessage}</p> : null}
              {setupWarnings.map((warning) => (
                <p className="muted" key={warning}>{warning}</p>
              ))}
              {setupErrors.map((error) => (
                <p className="error" key={error}>{error}</p>
              ))}
              <p className="muted">CLI fallback: `opencommotion setup`</p>
            </section>
          ) : (
            <section className="setup-panel setup-hidden-tip">
              <h3>Setup Hidden In Normal Mode</h3>
              <p className="muted">Open `/?setup=1` when you want to configure providers and auth.</p>
            </section>
          )}

          <section className="section-block run-panel">
            <h3>Agent Run Manager</h3>
            <div className="row">
              <button onClick={refreshRuns}>Refresh Runs</button>
              <button onClick={createRun} disabled={runActionLoading}>Create Run</button>
            </div>
            <select
              aria-label="run selector"
              value={selectedRunId}
              onChange={(e) => setSelectedRunId(e.target.value)}
            >
              <option value="">select run</option>
              {runs.map((run) => (
                <option value={run.run_id} key={run.run_id}>
                  {run.label} ({run.status})
                </option>
              ))}
            </select>
            {selectedRun ? (
              <p className="muted">
                queue: q={selectedRun.queue?.queued || 0} p={selectedRun.queue?.processing || 0} d={selectedRun.queue?.done || 0}
                {' '}e={selectedRun.queue?.error || 0}
              </p>
            ) : null}
            <input
              value={queuedPrompt}
              onChange={(e) => setQueuedPrompt(e.target.value)}
              placeholder="queue prompt"
            />
            <div className="row">
              <button onClick={enqueueToRun} disabled={!selectedRunId || runActionLoading}>Enqueue</button>
              <button onClick={() => controlRun('run_once')} disabled={!selectedRunId || runActionLoading}>Run Once</button>
              <button onClick={() => controlRun('drain')} disabled={!selectedRunId || runActionLoading}>Drain</button>
            </div>
            <div className="row">
              <button onClick={() => controlRun('pause')} disabled={!selectedRunId || runActionLoading}>Pause</button>
              <button onClick={() => controlRun('resume')} disabled={!selectedRunId || runActionLoading}>Resume</button>
              <button onClick={() => controlRun('stop')} disabled={!selectedRunId || runActionLoading}>Stop</button>
            </div>
          </section>

          <section className="section-block voice-panel">
            <h3>Voice Input</h3>
            <input
              aria-label="voice file"
              type="file"
              accept="audio/*"
              onChange={(e) => setAudioFile(e.target.files?.[0] || null)}
            />
            <button onClick={transcribeSelectedAudio} disabled={!audioFile || transcribing}>
              {transcribing ? 'Transcribing...' : 'Transcribe Audio'}
            </button>
            <p className="muted">{transcript || 'No transcript yet.'}</p>
          </section>

          <section className="section-block">
            <h3>Artifact Search</h3>
            <div className="row">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="search artifacts"
              />
              <select
                aria-label="search mode"
                value={searchMode}
                onChange={(e) => setSearchMode(e.target.value as 'lexical' | 'semantic' | 'hybrid')}
              >
                <option value="hybrid">hybrid</option>
                <option value="semantic">semantic</option>
                <option value="lexical">lexical</option>
              </select>
              <button onClick={searchArtifacts}>Search</button>
            </div>
            <ul className="results">
              {results.map((r) => (
                <li key={r.artifact_id}>
                  <div>{r.title}</div>
                  <small>
                    {r.match_mode || 'n/a'}
                    {typeof r.score === 'number' ? ` · ${r.score.toFixed(3)}` : ''}
                  </small>
                </li>
              ))}
            </ul>
          </section>

          <section className="section-block">
            <h3>Text Agent</h3>
            <p>{text || 'No response yet.'}</p>
          </section>

          <section className="section-block">
            <h3>Voice Agent</h3>
            <p>{describeVoice(voice)}</p>
            {toneFallback ? (
              <div>
                <p className="muted">Backend TTS is in tone fallback. Using browser speech instead.</p>
                <button onClick={() => speakInBrowser(text)} disabled={!text || browserSpeaking}>
                  {browserSpeaking ? 'Speaking...' : 'Speak In Browser'}
                </button>
              </div>
            ) : audioUri ? (
              <audio controls src={`${gateway}${audioUri}`} />
            ) : (
              <p className="muted">No audio yet.</p>
            )}
          </section>
        </div>
      </aside>
    </div>
  )
}

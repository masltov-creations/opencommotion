import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { buildScene, type Patch, type SceneActor } from './runtime/sceneRuntime'

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

type TurnResult = {
  session_id: string
  turn_id: string
  text: string
  voice: VoicePayload
  visual_patches: Patch[]
  timeline?: { duration_ms: number }
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

const gateway = (import.meta as { env?: Record<string, string> }).env?.VITE_GATEWAY_URL || 'http://127.0.0.1:8000'
const wsGateway = gateway.replace(/^http/i, 'ws')
const isTestMode = (import.meta as { env?: Record<string, string> }).env?.MODE === 'test'

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

function describeVoice(voice: VoicePayload | null): string {
  if (!voice) {
    return 'No voice output yet.'
  }
  return `${voice.voice}${voice.engine ? ` (${voice.engine})` : ''}`
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
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [transcript, setTranscript] = useState('')
  const [transcribing, setTranscribing] = useState(false)
  const [lastError, setLastError] = useState('')
  const [runtimeCaps, setRuntimeCaps] = useState<RuntimeCapabilities | null>(null)
  const [capsLoading, setCapsLoading] = useState(false)
  const [capsError, setCapsError] = useState('')

  const session = useMemo(() => `sess-${Math.random().toString(36).slice(2)}`, [])
  const lastTurnRef = useRef('')

  const refreshRuntimeCapabilities = useCallback(async () => {
    if (isTestMode) {
      return
    }
    setCapsLoading(true)
    setCapsError('')
    try {
      const res = await fetch(`${gateway}/v1/runtime/capabilities`)
      if (!res.ok) {
        throw new Error(`runtime capabilities failed (${res.status})`)
      }
      const data = (await res.json()) as RuntimeCapabilities
      setRuntimeCaps(data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown capability failure'
      setCapsError(msg)
    } finally {
      setCapsLoading(false)
    }
  }, [])

  function loadTurn(turn: TurnResult): void {
    if (!turn || turn.turn_id === lastTurnRef.current) {
      return
    }
    lastTurnRef.current = turn.turn_id
    setText(turn.text)
    setVoice(turn.voice)
    const orderedPatches = [...(turn.visual_patches || [])].sort((a, b) => (a.at_ms || 0) - (b.at_ms || 0))
    setPatches(orderedPatches)
    const totalDuration = calcDurationMs(turn)
    setDurationMs(totalDuration)
    setPlaybackMs(0)
    setPlaying(true)
  }

  async function runTurn() {
    setRunning(true)
    setLastError('')
    try {
      const res = await fetch(`${gateway}/v1/orchestrate`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ session_id: session, prompt }),
      })
      if (!res.ok) {
        throw new Error(`orchestrate failed (${res.status})`)
      }
      const data = (await res.json()) as TurnResult
      loadTurn(data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown run-turn failure'
      setLastError(msg)
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
        body,
      })
      if (!res.ok) {
        throw new Error(`transcribe failed (${res.status})`)
      }
      const data = (await res.json()) as { transcript: { final: string } }
      const finalText = data.transcript.final || ''
      setTranscript(finalText)
      if (finalText) {
        setPrompt(finalText)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown transcription failure'
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
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          title: `Turn ${new Date().toLocaleTimeString()}`,
          summary: text,
          tags: ['favorite', 'manual'],
          saved_by: 'ui',
        }),
      })
      if (!res.ok) {
        throw new Error(`save failed (${res.status})`)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown save failure'
      setLastError(msg)
    }
  }

  async function searchArtifacts() {
    setLastError('')
    try {
      const res = await fetch(
        `${gateway}/v1/artifacts/search?q=${encodeURIComponent(query)}&mode=${encodeURIComponent(searchMode)}`,
      )
      if (!res.ok) {
        throw new Error(`search failed (${res.status})`)
      }
      const data = (await res.json()) as { results: ArtifactResult[] }
      setResults(data.results)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown search failure'
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

    const ws = new WebSocket(`${wsGateway}/v1/events/ws`)
    const heartbeat = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 10000)

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as {
          payload?: TurnResult
          session_id?: string
          turn_id?: string
        }
        const payload = parsed.payload
        if (!payload) {
          return
        }
        if (payload.session_id !== session) {
          return
        }
        loadTurn(payload)
      } catch {
        // Ignore malformed ws events.
      }
    }

    return () => {
      window.clearInterval(heartbeat)
      ws.close()
    }
  }, [session])

  useEffect(() => {
    if (isTestMode) {
      return
    }
    refreshRuntimeCapabilities()
    const timer = window.setInterval(() => {
      refreshRuntimeCapabilities()
    }, 12000)
    return () => {
      window.clearInterval(timer)
    }
  }, [refreshRuntimeCapabilities])

  const scene = useMemo(() => buildScene(patches, playbackMs), [patches, playbackMs])
  const appliedCount = useMemo(
    () => patches.filter((patch) => (patch.at_ms || 0) <= playbackMs).length,
    [patches, playbackMs],
  )

  const actorEntries = Object.entries(scene.actors)
  const lineChart = scene.charts.adoption_curve
  const pieChart = scene.charts.saturation_pie
  const audioUri = voice?.segments?.[0]?.audio_uri
  const llmProvider = runtimeCaps?.llm?.selected_provider || 'unknown'
  const llmEffectiveProvider = runtimeCaps?.llm?.effective_provider || llmProvider
  const llmReady = runtimeCaps?.llm?.effective_ready === true
  const sttEngine = runtimeCaps?.voice?.stt?.selected_engine || 'unknown'
  const ttsEngine = runtimeCaps?.voice?.tts?.selected_engine || 'unknown'

  return (
    <div className="layout">
      <aside className="panel">
        <h1>OpenCommotion</h1>
        <p>Text + voice + motion synchronized visual computing.</p>
        <div className="setup-panel">
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
          </div>
          <p className="muted">Need guided setup? Run `make setup-wizard` in your terminal.</p>
        </div>
        <textarea rows={4} value={prompt} onChange={(e) => setPrompt(e.target.value)} />

        <div className="row">
          <button onClick={runTurn} disabled={running}>{running ? 'Running...' : 'Run Turn'}</button>
          <button onClick={saveArtifact} disabled={!text}>Save</button>
        </div>

        <div className="voice-panel">
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
        </div>

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

        {lastError ? <p className="error">{lastError}</p> : null}
      </aside>

      <main className="stage">
        <section className="card">
          <h2>Text Agent</h2>
          <p>{text || 'No response yet.'}</p>
        </section>

        <section className="card">
          <h2>Voice Agent</h2>
          <p>{describeVoice(voice)}</p>
          {audioUri ? <audio controls src={`${gateway}${audioUri}`} /> : <p className="muted">No audio yet.</p>}
        </section>

        <section className="card">
          <div className="row controls">
            <h2>Visual Stage</h2>
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

          <svg viewBox="0 0 720 360" aria-label="visual stage">
            <defs>
              <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#111827" />
                <stop offset="100%" stopColor="#0ea5e9" />
              </linearGradient>
            </defs>
            <rect x="0" y="0" width="720" height="360" fill="url(#bg)" rx="14" />

            <rect x="420" y="206" width="240" height="120" fill="rgba(2,6,23,0.58)" rx="12" />
            {lineChart?.points ? (
              <polyline
                points={mapPolyline(lineChart.points, 440, 220, 180, 80)}
                fill="none"
                stroke="#22d3ee"
                strokeWidth="4"
              />
            ) : null}

            {pieChart?.slices?.length ? (
              <g>
                <circle cx="615" cy="138" r="45" fill="#334155" />
                <text x="615" y="143" textAnchor="middle" fill="#e2e8f0" fontSize="13">
                  {pieChart.slices[0]?.label}: {pieChart.slices[0]?.value}%
                </text>
              </g>
            ) : null}

            {actorEntries.map(([id, actor]) => {
              const x = actor.x ?? 140
              const y = actor.y ?? 170

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

              return null
            })}

            <text x="24" y="32" fill="#e2e8f0" fontSize="20">Patch count: {patches.length}</text>
            <text x="24" y="56" fill="#cbd5e1" fontSize="14">Applied: {appliedCount}</text>
            <text x="24" y="80" fill="#cbd5e1" fontSize="14">Playback: {Math.round(playbackMs)}ms / {durationMs}ms</text>

            {scene.annotations.slice(-2).map((a, idx) => (
              <text key={`${a.text}-${idx}`} x="24" y={324 - idx * 20} fill="#f8fafc" fontSize="13">{a.text}</text>
            ))}
          </svg>
        </section>
      </main>
    </div>
  )
}

import { useMemo, useState } from 'react'

type Patch = { op: string; path: string }

type TurnResult = {
  text: string
  visual_patches: Patch[]
}

const gateway = 'http://127.0.0.1:8000'

export default function App() {
  const [prompt, setPrompt] = useState('show a moonwalk with adoption chart and pie')
  const [text, setText] = useState('')
  const [patches, setPatches] = useState<Patch[]>([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Array<{ artifact_id: string; title: string }>>([])
  const [running, setRunning] = useState(false)

  const session = useMemo(() => `sess-${Math.random().toString(36).slice(2)}`, [])

  async function runTurn() {
    setRunning(true)
    try {
      const res = await fetch(`${gateway}/v1/orchestrate`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ session_id: session, prompt }),
      })
      const data = (await res.json()) as TurnResult
      setText(data.text)
      setPatches(data.visual_patches)
    } finally {
      setRunning(false)
    }
  }

  async function saveArtifact() {
    await fetch(`${gateway}/v1/artifacts/save`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        title: `Turn ${new Date().toLocaleTimeString()}`,
        summary: text,
        tags: ['favorite', 'manual'],
        saved_by: 'ui',
      }),
    })
  }

  async function searchArtifacts() {
    const res = await fetch(`${gateway}/v1/artifacts/search?q=${encodeURIComponent(query)}`)
    const data = (await res.json()) as { results: Array<{ artifact_id: string; title: string }> }
    setResults(data.results)
  }

  return (
    <div className="layout">
      <aside className="panel">
        <h1>OpenCommotion</h1>
        <p>Text + voice + motion synchronized visual computing.</p>
        <textarea rows={4} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        <div className="row">
          <button onClick={runTurn} disabled={running}>{running ? 'Running...' : 'Run Turn'}</button>
          <button onClick={saveArtifact} disabled={!text}>Save</button>
        </div>
        <div className="row">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="search artifacts" />
          <button onClick={searchArtifacts}>Search</button>
        </div>
        <ul>
          {results.map((r) => (
            <li key={r.artifact_id}>{r.title}</li>
          ))}
        </ul>
      </aside>
      <main className="stage">
        <section className="card">
          <h2>Text Agent</h2>
          <p>{text || 'No response yet.'}</p>
        </section>
        <section className="card">
          <h2>Visual Stage</h2>
          <svg viewBox="0 0 720 360" aria-label="visual stage">
            <defs>
              <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#111827" />
                <stop offset="100%" stopColor="#0ea5e9" />
              </linearGradient>
            </defs>
            <rect x="0" y="0" width="720" height="360" fill="url(#bg)" rx="14" />
            <circle cx="160" cy="170" r="44" fill="#f59e0b" />
            <rect x="132" y="218" width="56" height="80" fill="#fef3c7" rx="10" />
            <text x="250" y="72" fill="#e2e8f0" fontSize="24">Patch count: {patches.length}</text>
            <text x="250" y="108" fill="#cbd5e1" fontSize="14">{patches[0]?.path || '/actors/guide'}</text>
          </svg>
        </section>
      </main>
    </div>
  )
}

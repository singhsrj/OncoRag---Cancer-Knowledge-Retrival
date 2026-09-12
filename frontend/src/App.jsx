import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const SAMPLE_QUESTIONS = [
  'What are the risk factors for lung cancer?',
  'How is breast cancer typically diagnosed?',
  'What causes cervical cancer?',
]

function formatTopic(topic) {
  if (!topic) return ''
  return topic
    .split('_')
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(' ')
}

export default function App() {
  const [topics, setTopics] = useState([])
  const [topicsError, setTopicsError] = useState(null)
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(3)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const inputRef = useRef(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/topics/`)
      .then((r) => {
        if (!r.ok) throw new Error(`Server responded ${r.status}`)
        return r.json()
      })
      .then((data) => setTopics(data.topics || []))
      .catch((err) =>
        setTopicsError(
          err.message === 'Failed to fetch'
            ? `Can't reach the API at ${API_BASE}. Is the Django server running?`
            : err.message
        )
      )
  }, [])

  async function runQuery(q) {
    const questionText = (q ?? query).trim()
    if (!questionText || loading) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await fetch(`${API_BASE}/api/query/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: questionText, top_k: topK }),
      })
      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.error || `Server responded ${res.status}`)
      }

      setResult(data)
      setHistory((h) => [{ query: questionText, topic: data.topic }, ...h].slice(0, 6))
    } catch (err) {
      setError(
        err.message === 'Failed to fetch'
          ? `Can't reach the API at ${API_BASE}. Is the Django server running?`
          : err.message
      )
    } finally {
      setLoading(false)
    }
  }

  function handleSubmit(e) {
    e.preventDefault()
    runQuery()
  }

  return (
    <div className="page">
      <header className="topbar">
        <div className="topbar-mark">
          <span className="mark-dot" aria-hidden="true" />
          OncoRag
        </div>
        <div className="topbar-sub">Cancer knowledge retrieval</div>
      </header>

      <main className="layout">
        <section className="query-panel">
          <h1>Ask a question about a cancer topic</h1>
          <p className="lede">
            Each question is routed to the most relevant source document,
            then answered strictly from the retrieved context.
          </p>

          <form onSubmit={handleSubmit} className="query-form">
            <textarea
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. What are the risk factors for lung cancer?"
              rows={3}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  runQuery()
                }
              }}
            />
            <div className="form-row">
              <label className="topk-control">
                top_k
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value) || 1)}
                />
              </label>
              <button type="submit" disabled={loading || !query.trim()}>
                {loading ? 'Searching…' : 'Ask'}
              </button>
            </div>
          </form>

          <div className="samples">
            <span className="samples-label">Try:</span>
            {SAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                type="button"
                className="sample-chip"
                onClick={() => {
                  setQuery(q)
                  runQuery(q)
                }}
              >
                {q}
              </button>
            ))}
          </div>

          <div className="topics-block">
            <span className="topics-label">Knowledge base</span>
            {topicsError ? (
              <p className="topics-error">{topicsError}</p>
            ) : topics.length === 0 ? (
              <p className="topics-loading">Loading topics…</p>
            ) : (
              <ul className="topics-list">
                {topics.map((t) => (
                  <li key={t}>{formatTopic(t)}</li>
                ))}
              </ul>
            )}
          </div>

          {history.length > 0 && (
            <div className="history-block">
              <span className="topics-label">Recent</span>
              <ul className="history-list">
                {history.map((h, i) => (
                  <li key={i}>
                    <button type="button" onClick={() => { setQuery(h.query); runQuery(h.query) }}>
                      {h.query}
                    </button>
                    <span className="history-topic">{formatTopic(h.topic)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <section className="answer-panel">
          {loading && (
            <div className="state state-loading">
              <div className="pulse" aria-hidden="true" />
              <p>Routing your question, retrieving context, generating an answer…</p>
            </div>
          )}

          {!loading && error && (
            <div className="state state-error">
              <p className="state-title">Something went wrong</p>
              <p>{error}</p>
            </div>
          )}

          {!loading && !error && !result && (
            <div className="state state-empty">
              <p className="state-title">No answer yet</p>
              <p>Ask a question on the left and the answer will appear here, grounded in the retrieved source passages.</p>
            </div>
          )}

          {!loading && !error && result && (
            <article className="answer">
              <div className="answer-meta">
                <span className="topic-pill">{formatTopic(result.topic)}</span>
                <span className="meta-query">&ldquo;{result.query}&rdquo;</span>
              </div>

              <p className="answer-text">{result.answer}</p>

              {result.sources?.length > 0 && (
                <div className="sources">
                  <span className="sources-label">
                    Sources ({result.sources.length})
                  </span>
                  <ol className="sources-list">
                    {result.sources.map((s, i) => (
                      <li key={i}>
                        <span className="source-section">{s.section || 'Untitled section'}</span>
                        <span className="source-meta">
                          {s.source}{s.page ? ` · p.${s.page}` : ''}
                        </span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </article>
          )}
        </section>
      </main>
    </div>
  )
}

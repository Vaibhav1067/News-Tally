import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { ClaimInput, EXAMPLES } from '../components/ClaimInput'
import { RiskSummary } from '../components/analysis/RiskSummary'
import { MatchList } from '../components/analysis/MatchList'
import { ClassifierPanel, EvidenceTimeline, ExplanationPanel, FeedbackBar, ScoreBreakdown, SourcePanel } from '../components/analysis/Panels'
import { ErrorNote, Panel } from '../components/ui'
import { api, type AnalyzeInput } from '../services/api'
import type { AnalyzeResponse } from '../types/api'
import { useAsync } from '../hooks/useAsync'
import { nf } from '../utils/format'

const STAGES = ['Validate input', 'Extract content', 'Detect language', 'Search fact-checks', 'Classify text',
  'Profile source', 'Explain model', 'Assess risk']

function Stages({ state, ms }: { state: 'running' | 'done'; ms?: number }) {
  return (
    <p aria-live="polite" className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted">
      {state === 'running' && <Loader2 className="size-3.5 animate-spin" aria-hidden />}
      <span className="font-medium text-ink">{state === 'running' ? 'Checking the claim…' : `Checked in ${(ms ?? 0).toLocaleString('en-IN')} ms.`}</span>
      <span>{STAGES.join(' · ')}</span>
    </p>
  )
}

export default function Analyze() {
  const loc = useLocation()
  const qs = new URLSearchParams(loc.search)
  const initial = (loc.state as { input?: AnalyzeInput } | null)?.input
    ?? (qs.get('text') ? { text: qs.get('text')! } : qs.get('url') ? { url: qs.get('url')! } : undefined)
  const [input, setInput] = useState<AnalyzeInput | undefined>(initial)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [formKey, setFormKey] = useState(0)
  const resultRef = useRef<HTMLDivElement>(null)
  const health = useAsync(() => api.health(), [])

  async function run(i: AnalyzeInput) {
    setInput(i); setBusy(true); setError(null); setResult(null)
    try {
      const r = await api.analyze(i)
      setResult(r)
      requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  useEffect(() => { if (initial) run(initial) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="mx-auto max-w-[1160px] px-5 pt-8 md:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-[26px] font-semibold tracking-[-0.015em]">Check a claim</h1>
          <p className="mt-1 text-[14px] text-muted">Checked against {health.data ? nf.format(health.data.fact_checks_loaded) : 'the collected'} Factly and Alt News fact-checks in English, Hindi and Kannada.</p>
        </div>
      </div>

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1fr_320px]">
        <ClaimInput key={formKey} onSubmit={run} busy={busy} initial={input} compact={!!result} />
        <aside aria-label="Example claims" className="rounded-card border border-border bg-surface p-5">
          <h2 className="text-[13px] font-semibold">Try an example</h2>
          <ul className="mt-2 divide-y divide-rule">
            {EXAMPLES.map((ex) => (
              <li key={ex.label}>
                <button type="button" disabled={busy} onClick={() => { setFormKey((k) => k + 1); run({ text: ex.text }) }}
                  className="w-full py-2.5 text-left transition hover:text-accent-ink disabled:opacity-50">
                  <div className="text-[13px] font-medium">{ex.label}</div>
                  <div className="line-clamp-1 text-[12px] text-muted">{ex.text}</div>
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>

      <div ref={resultRef} className="scroll-mt-20 pt-6">
        {busy && <Stages state="running" />}
        {error && <ErrorNote message={error} onRetry={input ? () => run(input) : undefined} />}
        {!busy && !error && !result && (
          <p className="rounded-card border border-dashed border-control px-5 py-8 text-center text-[13px] text-muted">
            Results appear here: the assessment, the matching fact-checks, the source profile and why the model scored the text as it did.
          </p>
        )}
        <>
          {result && (
            <div key={result.analysis_id} className="space-y-6">
              <div><Stages state="done" ms={result.processing_time_ms} /></div>
              {result.extracted_content.extraction_error && (
                <ErrorNote message={`URL could not be read (${result.extracted_content.extraction_error}); analysed the pasted text only.`} />
              )}
              <div><RiskSummary r={result} /></div>

              <div className="grid gap-6 lg:grid-cols-[1.55fr_1fr]">
                <div>
                  <Panel title="Matching fact-checks" aside={`similarity = retrieval relevance, not proof · ${result.retrieval_backend}`}>
                    <MatchList matches={result.matching_fact_checks} backend={result.retrieval_backend} />
                  </Panel>
                </div>
                <div className="space-y-6">
                  <div><Panel title="How is this calculated?"><ScoreBreakdown ra={result.risk_assessment} /></Panel></div>
                  <div><Panel title="Evidence timeline"><EvidenceTimeline matches={result.matching_fact_checks} /></Panel></div>
                </div>
              </div>

              <div className="grid gap-6 lg:grid-cols-[1.55fr_1fr]">
                <div><Panel title="Explainability" aside="SHAP · model behaviour, not proof"><ExplanationPanel e={result.explanation} /></Panel></div>
                <div className="space-y-6">
                  <div><Panel title="Content classifier"><ClassifierPanel p={result.prediction} /></Panel></div>
                  <div><Panel title="Source information"><SourcePanel s={result.source_information} /></Panel></div>
                </div>
              </div>

              <div className="flex flex-col gap-4 rounded-card border border-border bg-surface px-5 py-4 md:flex-row md:items-center md:justify-between">
                <FeedbackBar r={result} />
                <p className="text-[12px] text-muted md:max-w-[52ch] md:text-right">{result.disclaimer} {result.stored ? 'This text was saved to history.' : 'Your text was not stored.'}</p>
              </div>
            </div>
          )}
        </>
      </div>
    </div>
  )
}

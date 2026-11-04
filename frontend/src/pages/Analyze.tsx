import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Check, Loader2 } from 'lucide-react'
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
    <div aria-live="polite" className="rounded-[6px] border border-border bg-surface px-5 py-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-[13px] font-semibold">{state === 'running' ? 'Running the pipeline' : 'Pipeline complete'}</h2>
        <span className="tnum text-[12px] text-muted">{state === 'done' && ms != null ? `${ms.toLocaleString('en-IN')} ms on the server` : 'one request; stages run server-side'}</span>
      </div>
      <ol className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-[13px]">
        {STAGES.map((s) => (
          <li key={s} className={`flex items-center gap-1.5 ${state === 'done' ? 'text-ink' : 'text-muted'}`}>
            {state === 'done' ? <Check className="size-3.5 text-positive" aria-hidden /> : <Loader2 className="size-3.5 animate-spin" aria-hidden />}
            {s}
          </li>
        ))}
      </ol>
    </div>
  )
}

const rise = { hidden: { opacity: 0, y: 18 }, show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.07, duration: 0.4, ease: [0.2, 0.7, 0.2, 1] as const } }) }

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
    <div className="mx-auto max-w-[1320px] px-5 pt-8 md:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-bold tracking-[-0.015em]">Analyze a claim</h1>
          <p className="mt-1 text-[14px] text-muted">Checked against {health.data ? nf.format(health.data.fact_checks_loaded) : 'the collected'} Factly and Alt News fact-checks in English, Hindi and Kannada.</p>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        <ClaimInput key={formKey} onSubmit={run} busy={busy} initial={input} compact={!!result} />
        <aside aria-label="Example claims" className="rounded-[6px] border border-border bg-surface p-5">
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
          <p className="rounded-[6px] border border-dashed border-control px-5 py-8 text-center text-[13px] text-muted">
            Results appear here: the assessment, the matching fact-checks, the source profile and why the model scored the text as it did.
          </p>
        )}
        <AnimatePresence>
          {result && (
            <motion.div key={result.analysis_id} initial="hidden" animate="show" className="space-y-6">
              <motion.div variants={rise} custom={0}><Stages state="done" ms={result.processing_time_ms} /></motion.div>
              {result.extracted_content.extraction_error && (
                <ErrorNote message={`URL could not be read (${result.extracted_content.extraction_error}); analysed the pasted text only.`} />
              )}
              <motion.div variants={rise} custom={1}><RiskSummary r={result} /></motion.div>

              <div className="grid gap-6 lg:grid-cols-[1.55fr_1fr]">
                <motion.div variants={rise} custom={2}>
                  <Panel title="Matching fact-checks" aside={`similarity = retrieval relevance, not proof · ${result.retrieval_backend}`}>
                    <MatchList matches={result.matching_fact_checks} backend={result.retrieval_backend} />
                  </Panel>
                </motion.div>
                <div className="space-y-6">
                  <motion.div variants={rise} custom={3}><Panel title="How is this calculated?"><ScoreBreakdown ra={result.risk_assessment} /></Panel></motion.div>
                  <motion.div variants={rise} custom={4}><Panel title="Evidence timeline"><EvidenceTimeline matches={result.matching_fact_checks} /></Panel></motion.div>
                </div>
              </div>

              <div className="grid gap-6 lg:grid-cols-[1.55fr_1fr]">
                <motion.div variants={rise} custom={5}><Panel title="Explainability" aside="SHAP · model behaviour, not proof"><ExplanationPanel e={result.explanation} /></Panel></motion.div>
                <div className="space-y-6">
                  <motion.div variants={rise} custom={6}><Panel title="Content classifier"><ClassifierPanel p={result.prediction} /></Panel></motion.div>
                  <motion.div variants={rise} custom={7}><Panel title="Source information"><SourcePanel s={result.source_information} /></Panel></motion.div>
                </div>
              </div>

              <div className="flex flex-col gap-4 rounded-[6px] border border-border bg-surface px-5 py-4 md:flex-row md:items-center md:justify-between">
                <FeedbackBar r={result} />
                <p className="text-[12px] text-muted md:max-w-[52ch] md:text-right">{result.disclaimer} {result.stored ? 'This text was saved to history.' : 'Your text was not stored.'}</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

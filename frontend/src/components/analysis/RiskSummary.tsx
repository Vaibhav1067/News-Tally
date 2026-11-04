import { motion } from 'framer-motion'
import type { AnalyzeResponse } from '../../types/api'
import { RISK_TITLE, langName, riskTone } from '../../utils/format'
import { Pill } from '../ui'

const LEVEL_INK = { neg: 'text-neg-ink', warn: 'text-warn-ink', pos: 'text-pos-ink', neu: 'text-ink' }
const SCALE_FILL = { neg: 'bg-negative', warn: 'bg-warning', pos: 'bg-positive', neu: 'bg-ink/60' }

/** The answer to the screen's one question: what does the evidence say about this claim? */
export function RiskSummary({ r, embedded = false }: { r: AnalyzeResponse; embedded?: boolean }) {
  const Title = embedded ? 'p' : 'h2'
  const Sub = embedded ? 'p' : 'h3'
  const ra = r.risk_assessment
  const tone = riskTone(ra.level)
  const lang = r.detected_language
  return (
    <section data-ui={embedded || undefined} aria-labelledby="risk-h" className="rounded-[6px] border border-border bg-surface p-5 md:p-6">
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <p className="text-[13px] text-muted">Assessment</p>
          <Title id="risk-h" className={`mt-1 text-[28px] leading-tight font-semibold tracking-[-0.015em] ${LEVEL_INK[tone]}`}>
            {RISK_TITLE[ra.level]}
          </Title>
          <p className="mt-3 max-w-[60ch] text-[15px] leading-relaxed text-ink">{ra.summary}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Pill title={`Detected by ${lang.method}`}>{lang.is_mixed ? lang.name : langName(lang.code)} · {(lang.confidence * 100).toFixed(0)}% confidence</Pill>
            {!lang.supported_by_model && <Pill tone="warn">Language not in training data</Pill>}
            {r.extracted_content.source !== 'text' && <Pill>Extracted from URL</Pill>}
            {r.extracted_content.truncated && <Pill tone="warn">Text truncated to 10,000 characters</Pill>}
          </div>
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-5 self-start">
          <div className="col-span-2">
            <dt className="text-[13px] text-muted">Risk index</dt>
            <dd className="mt-1 flex items-baseline gap-2">
              <span className="tnum text-[32px] leading-none font-semibold">{ra.risk_score.toFixed(0)}</span>
              <span className="text-[13px] text-muted">of 100 · heuristic, not a probability</span>
            </dd>
            <div className="relative mt-3 h-1.5 rounded-full bg-raised" role="img" aria-label={`Risk index ${ra.risk_score.toFixed(0)} of 100`}>
              <motion.div className={`h-1.5 rounded-full ${SCALE_FILL[tone]}`} initial={{ width: 0 }}
                animate={{ width: `${ra.risk_score}%` }} transition={{ duration: 0.7, ease: [0.2, 0.7, 0.2, 1] }} />
              <span className="absolute top-[-3px] h-3 w-px bg-muted" style={{ left: '50%' }} title="50 = no evidence either way" />
            </div>
            <div className="tnum mt-1 flex justify-between text-[13px] text-muted"><span>0</span><span>50 neutral</span><span>100</span></div>
          </div>
          <div>
            <dt className="text-[13px] text-muted">Evidence strength</dt>
            <dd className="tnum mt-1 text-[20px] font-semibold">{ra.evidence_strength_label} <span className="text-[13px] font-normal text-muted">{ra.evidence_strength.toFixed(2)}</span></dd>
          </div>
          <div>
            <dt className="text-[13px] text-muted">Processed in</dt>
            <dd className="tnum mt-1 text-[20px] font-semibold">{r.processing_time_ms.toLocaleString('en-IN')} <span className="text-[13px] font-normal text-muted">ms</span></dd>
          </div>
        </dl>
      </div>
      <div className="mt-6 grid gap-6 border-t border-border pt-5 md:grid-cols-2">
        <div>
          <Sub className="text-[13px] font-semibold">Why this assessment</Sub>
          <ul className="mt-2 space-y-2 text-[13px] leading-relaxed text-ink">
            {ra.reasons.map((x) => <li key={x} className="flex gap-2"><span className="mt-2 size-1 shrink-0 rounded-full bg-accent" />{x}</li>)}
          </ul>
        </div>
        <div>
          <Sub className="text-[13px] font-semibold">Missing evidence</Sub>
          {ra.missing_evidence.length ? (
            <ul className="mt-2 space-y-2 text-[13px] leading-relaxed text-muted">
              {ra.missing_evidence.map((x) => <li key={x} className="flex gap-2"><span className="mt-2 size-1 shrink-0 rounded-full bg-warning" />{x}</li>)}
            </ul>
          ) : <p className="mt-2 text-[13px] text-muted">Every dimension had evidence available.</p>}
        </div>
      </div>
    </section>
  )
}

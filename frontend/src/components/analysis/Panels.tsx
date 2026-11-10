import { useState } from 'react'
import type { AnalyzeResponse, Explanation, FactCheckMatch, Prediction, RiskAssessment, SourceInfo } from '../../types/api'
import { ageText, verdictLabel, verdictTone } from '../../utils/format'
import { api } from '../../services/api'
import { Bar, KV, Pill } from '../ui'

/* ---------- Content classification ---------- */
export function ClassifierPanel({ p }: { p: Prediction }) {
  if (!p.available) return <p className="text-[13px] text-muted">{p.note || 'The classifier is not loaded.'}</p>
  const rows = Object.entries(p.probabilities).sort((a, b) => b[1] - a[1])
  return (
    <div>
      <dl className="space-y-3">
        {rows.map(([k, v]) => (
          <div key={k}>
            <div className="flex justify-between text-[13px]">
              <dt className={k === p.label ? 'font-semibold text-ink' : 'text-muted'}>{verdictLabel(k)}</dt>
              <dd className="tnum">{(v * 100).toFixed(1)}%</dd>
            </div>
            <div className="mt-1.5"><Bar value={v} tone={k === p.label ? 'accent' : 'ink'} label={`${verdictLabel(k)} ${(v * 100).toFixed(1)}%`} /></div>
          </div>
        ))}
      </dl>
      {!p.in_domain && <p className="mt-4 rounded-card bg-warn-bg px-3 py-2 text-[12px] text-warn-ink">Not applied to the assessment: the text is too short or in a language the model was not trained on.</p>}
      <p className="mt-4 text-[12px] leading-relaxed text-muted">{p.note}</p>
      <p className="mt-2 text-[12px] text-muted">Model: {p.model_name?.replace(/_/g, ' ')} · TF-IDF word + character n-grams</p>
    </div>
  )
}

/* ---------- Explainability ---------- */
export function ExplanationPanel({ e }: { e: Explanation }) {
  if (!e.available) return <p className="text-[13px] text-muted">Explanation unavailable: {e.reason ?? 'no supported explanation method for this model.'}</p>
  const max = Math.max(...e.token_highlights.map((t) => Math.abs(t.score)), 1e-6)
  const feats = e.top_features.slice(0, 10)
  const fmax = Math.max(...feats.map((f) => Math.abs(f.contribution)), 1e-6)
  return (
    <div>
      <p className="text-[13px] text-muted">Words that pushed the model towards <span className="font-semibold text-ink">{verdictLabel(e.target_class)}</span> are shaded blue; words that pushed away are underlined grey.</p>
      <p className="mt-3 rounded-card bg-ground p-4 text-[15px] leading-[1.9]" lang="und">
        {e.token_highlights.slice(0, 160).map((t, i) => {
          const a = Math.abs(t.score) / max
          return (
            <span key={i} title={t.score ? `SHAP ${t.score.toFixed(3)}` : undefined}
              style={t.score > 0 ? { backgroundColor: `rgba(29,95,191,${0.12 + a * 0.5})` } : undefined}
              className={`rounded-[3px] px-[2px] ${t.score < 0 ? 'underline decoration-muted decoration-2 underline-offset-4' : ''}`}>
              {t.token}{' '}
            </span>
          )
        })}
      </p>
      <table className="mt-5 w-full text-[13px]">
        <caption className="sr-only">Top features by SHAP value</caption>
        <thead><tr className="text-left text-[12px] text-muted"><th className="pb-2 font-normal">Feature</th><th className="pb-2 font-normal">Type</th><th className="w-[40%] pb-2 font-normal">Contribution</th><th className="pb-2 text-right font-normal">SHAP</th></tr></thead>
        <tbody>
          {feats.map((f, i) => (
            <tr key={i} className="border-t border-rule">
              <td className="py-2 pr-3 font-medium whitespace-pre">“{f.feature}”</td>
              <td className="py-2 pr-3 text-muted">{f.kind === 'word' ? 'word n-gram' : 'character n-gram'}</td>
              <td className="py-2 pr-3">
                <div className="flex h-1.5 items-center">
                  <div className={`h-1.5 rounded-full ${f.contribution > 0 ? 'bg-accent' : 'bg-control'}`} style={{ width: `${(Math.abs(f.contribution) / fmax) * 100}%` }} />
                </div>
              </td>
              <td className="tnum py-2 text-right">{f.contribution > 0 ? '+' : '−'}{Math.abs(f.contribution).toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-4 text-[12px] leading-relaxed text-muted">{e.note} Method: {e.method === 'exact_linear_shap' ? 'exact linear SHAP (interventional), verified against the shap library in tests' : e.method}.</p>
    </div>
  )
}

/* ---------- Source information ---------- */
export function SourcePanel({ s }: { s: SourceInfo }) {
  if (s.status === 'no_url') return <p className="text-[13px] text-muted">No URL was submitted, so there is no source to profile. Paste an article link to see what the dataset records about its outlet.</p>
  return (
    <div className="text-[13px]">
      <dl>
        <KV k="Domain" v={s.domain ?? '—'} />
        {s.name && <KV k="Outlet" v={s.name} />}
        {s.source_type && <KV k="Type" v={s.source_type.replace('_', ' ')} />}
        <KV k="Fact-checks mentioning it" v={s.mentions_in_dataset} />
      </dl>
      <p className="mt-3 leading-relaxed">{s.coverage_note}</p>
      {Object.keys(s.verdict_breakdown).length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(s.verdict_breakdown).map(([v, n]) => <Pill key={v} tone={verdictTone(v)}>{verdictLabel(v)} {n}</Pill>)}
        </div>
      )}
      {s.example_fact_checks.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {s.example_fact_checks.slice(0, 3).map((x) => <li key={x.id}><a className="text-ink underline decoration-control underline-offset-2 hover:text-accent-ink" href={x.url} target="_blank" rel="noreferrer">{x.title}</a></li>)}
        </ul>
      )}
      {s.limitations.length > 0 && <ul className="mt-4 space-y-1 text-[12px] text-muted">{s.limitations.map((l) => <li key={l}>{l}</li>)}</ul>}
    </div>
  )
}

/* ---------- How is this calculated ---------- */
export function ScoreBreakdown({ ra }: { ra: RiskAssessment }) {
  const total = ra.components.reduce((a, c) => a + (c.value ?? 0.5) * c.weight, 0) * 100
  return (
    <div className="text-[13px]">
      <table className="w-full">
        <thead><tr className="text-left text-[12px] text-muted"><th className="pb-2 font-normal">Dimension</th><th className="pb-2 pl-3 text-right font-normal">Signal</th><th className="pb-2 pl-3 text-right font-normal">Weight</th><th className="pb-2 pl-3 text-right font-normal">Points</th></tr></thead>
        <tbody>
          {ra.components.map((c) => (
            <tr key={c.name} className="border-t border-rule align-top">
              <td className="py-2.5 pr-3"><div className="font-medium">{c.name}</div><div className="mt-0.5 text-[12px] text-muted">{c.detail}</div></td>
              <td className="tnum py-2.5 pl-3 text-right">{c.value?.toFixed(3) ?? '—'}</td>
              <td className="tnum py-2.5 pl-3 text-right">{c.weight.toFixed(2)}</td>
              <td className="tnum py-2.5 pl-3 text-right">{((c.value ?? 0.5) * c.weight * 100).toFixed(1)}</td>
            </tr>
          ))}
          <tr className="border-t border-border"><td className="py-2.5 font-semibold" colSpan={3}>Risk index</td><td className="tnum py-2.5 text-right font-semibold">{total.toFixed(1)}</td></tr>
        </tbody>
      </table>
      <p className="mt-3 leading-relaxed text-muted">{ra.formula}</p>
      <p className="mt-2 leading-relaxed text-muted">The outcome label is decided by rules, not by the number: a strong fact-check match decides it; the classifier alone can never produce “High misinformation risk”. Full derivation on the Methodology page.</p>
    </div>
  )
}

/* ---------- Evidence timeline ---------- */
export function EvidenceTimeline({ matches }: { matches: FactCheckMatch[] }) {
  const dated = matches.filter((m) => m.publication_date && m.match_strength !== 'weak')
    .sort((a, b) => (a.publication_date! < b.publication_date! ? -1 : 1))
  if (!dated.length) return <p className="text-[13px] text-muted">No strong or related fact-checks with a date, so there is no evidence timeline for this claim.</p>
  return (
    <ol className="relative ml-1 border-l border-control pl-5">
      {dated.map((m) => (
        <li key={m.id} className="relative pb-4 last:pb-0">
          <span className={`absolute top-1.5 -left-[24px] size-[7px] rounded-full ${verdictTone(m.verdict) === 'neg' ? 'bg-negative' : verdictTone(m.verdict) === 'warn' ? 'bg-warning' : 'bg-ink'}`} />
          <div className="tnum text-[12px] text-muted">{m.publication_date} · {ageText(m.age_days)} · {m.source_name}</div>
          <div className="mt-0.5 text-[13px] leading-snug">{m.title}</div>
        </li>
      ))}
    </ol>
  )
}

/* ---------- Feedback ---------- */
export function FeedbackBar({ r }: { r: AnalyzeResponse }) {
  const [sent, setSent] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const send = (t: string) => api.feedback(r.analysis_id, t).then(() => setSent(t)).catch((e) => setErr(e.message))
  if (sent) return <p className="text-[13px] text-muted">Thanks — feedback recorded against analysis {r.analysis_id.slice(0, 8)}.</p>
  return (
    <div className="flex flex-wrap items-center gap-2 text-[13px]">
      <span className="mr-1 text-muted">Was this useful?</span>
      {[['helpful', 'Helpful'], ['not_helpful', 'Not helpful'], ['wrong_match', 'Wrong match'], ['wrong_assessment', 'Wrong assessment']].map(([k, l]) => (
        <button key={k} onClick={() => send(k)} className="h-[30px] rounded-ctl border border-control px-3 text-ink transition hover:border-muted active:scale-[0.97]">{l}</button>
      ))}
      {err && <span className="text-neg-ink">{err}</span>}
    </div>
  )
}

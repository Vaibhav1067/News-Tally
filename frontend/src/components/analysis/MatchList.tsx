import { ExternalLink } from 'lucide-react'
import type { FactCheckMatch } from '../../types/api'
import { ageText, fmtDate, langName, verdictLabel, verdictTone } from '../../utils/format'
import { Pill } from '../ui'

const STRENGTH: Record<FactCheckMatch['match_strength'], string> = {
  strong: 'Strong match', related: 'Related', weak: 'Weak',
}

export function MatchList({ matches, backend }: { matches: FactCheckMatch[]; backend: string }) {
  if (backend === 'unavailable')
    return <p className="text-[13px] text-muted">The retrieval index is not built on this server, so no fact-checks could be searched.</p>
  if (!matches.length) return <p className="text-[13px] text-muted">No fact-checks returned.</p>
  return (
    <ol className="divide-y divide-rule">
      {matches.map((m, i) => (
        <li key={m.id} className={`grid gap-x-4 gap-y-2 py-4 first:pt-0 sm:grid-cols-[1fr_auto] ${m.match_strength === 'weak' ? 'opacity-70' : ''}`}>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Pill tone={verdictTone(m.verdict)}>{verdictLabel(m.verdict)}</Pill>
              <span className="text-[12px] text-muted">{m.source_name} · {langName(m.language)} · {fmtDate(m.publication_date)} ({ageText(m.age_days)})</span>
            </div>
            <a href={m.original_url} target="_blank" rel="noreferrer"
              className="group mt-2 flex items-start gap-1.5 text-[15px] leading-snug font-medium text-ink hover:text-accent-ink">
              <span>{i + 1}. {m.title ?? m.claim_text}</span>
              <ExternalLink className="mt-1 size-3.5 shrink-0 text-muted group-hover:text-accent-ink" aria-label="opens original fact-check" />
            </a>
            {m.claim_text && m.claim_text !== m.title && <p className="mt-1 text-[13px] text-muted">Claim as circulated: {m.claim_text}</p>}
            {m.explanation && <p className="mt-1 text-[13px] leading-relaxed text-ink/85">{m.explanation}</p>}
          </div>
          <div className="tnum flex items-center gap-3 sm:block sm:text-right">
            <div className="text-[18px] font-semibold">{m.similarity.toFixed(2)}</div>
            <div className={`text-[12px] ${m.match_strength === 'strong' ? 'text-accent-ink' : 'text-muted'}`}>{STRENGTH[m.match_strength]}</div>
          </div>
        </li>
      ))}
    </ol>
  )
}

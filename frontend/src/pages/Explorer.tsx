import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ExternalLink, Search } from 'lucide-react'
import { api } from '../services/api'
import { useAsync } from '../hooks/useAsync'
import { ErrorNote, Pill, Spinner } from '../components/ui'
import { fmtDate, langName, nf, verdictLabel, verdictTone } from '../utils/format'

const PAGE_SIZE = 20

function Select({ label, value, onChange, options, render = (v: string) => v }: {
  label: string; value: string; onChange: (v: string) => void; options: string[]; render?: (v: string) => string
}) {
  return (
    <label className="flex flex-col gap-1 text-[12px] text-muted">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="h-[34px] rounded-full border border-control bg-ground px-3 text-[13px] text-ink">
        <option value="">All</option>
        {options.map((o) => <option key={o} value={o}>{render(o)}</option>)}
      </select>
    </label>
  )
}

export default function Explorer() {
  const [params, setParams] = useSearchParams()
  const get = (k: string) => params.get(k) ?? ''
  const page = Number(params.get('page') ?? 1)
  const [q, setQ] = useState(get('q'))
  useEffect(() => { setQ(get('q')) }, [params]) // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params)
    if (v) next.set(k, v); else next.delete(k)
    if (k !== 'page') next.delete('page')
    setParams(next)
  }

  const facets = useAsync(() => api.facets(), [])
  const list = useAsync(() => api.factChecks({
    q: get('q'), language: get('language'), verdict: get('verdict'), source: get('source'), category: get('category'),
    date_from: get('date_from'), date_to: get('date_to'), page, page_size: PAGE_SIZE,
  }), [params.toString()])

  const total = list.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const f = facets.data

  return (
    <div className="mx-auto max-w-[1320px] px-5 pt-8 md:px-8">
      <h1 className="text-[26px] font-bold tracking-[-0.015em]">Fact-check explorer</h1>
      <p className="mt-1 text-[14px] text-muted">Every collected fact-check, linked to the original article. Verdicts were parsed from headlines and conclusions by transparent rules; “Not parsed” means the rules did not match.</p>

      <form onSubmit={(e) => { e.preventDefault(); set('q', q.trim()) }} className="mt-6 flex items-center gap-3 rounded-full border border-control bg-surface px-4">
        <Search className="size-4 text-muted" aria-hidden />
        <label htmlFor="q" className="sr-only">Search fact-checks</label>
        <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search claims, headlines and conclusions — e.g. deepfake, ₹500, बांग्लादेश"
          className="h-11 flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted" />
        <button className="text-[13px] font-semibold text-accent-ink hover:text-ink">Search</button>
      </form>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-6">
        <Select label="Language" value={get('language')} onChange={(v) => set('language', v)} options={f?.languages ?? []} render={langName} />
        <Select label="Verdict" value={get('verdict')} onChange={(v) => set('verdict', v)} options={f?.verdicts ?? []} render={verdictLabel} />
        <Select label="Source" value={get('source')} onChange={(v) => set('source', v)} options={f?.sources ?? []} />
        <Select label="Category" value={get('category')} onChange={(v) => set('category', v)} options={f?.categories ?? []} />
        <label className="flex flex-col gap-1 text-[12px] text-muted">From
          <input type="date" value={get('date_from')} onChange={(e) => set('date_from', e.target.value)} className="h-[34px] rounded-full border border-control bg-ground px-3 text-[13px] text-ink" />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-muted">To
          <input type="date" value={get('date_to')} onChange={(e) => set('date_to', e.target.value)} className="h-[34px] rounded-full border border-control bg-ground px-3 text-[13px] text-ink" />
        </label>
      </div>

      <div className="mt-6 flex items-baseline justify-between">
        <h2 className="text-[20px] text-muted"><span className="tnum text-ink">{nf.format(total)}</span> fact-checks</h2>
        {params.toString() && <button onClick={() => setParams(new URLSearchParams())} className="text-[13px] text-muted underline underline-offset-2 hover:text-ink">Clear filters</button>}
      </div>

      {list.error && <div className="mt-4"><ErrorNote message={list.error} onRetry={list.reload} /></div>}
      {list.loading && !list.data && <Spinner label="Loading fact-checks" />}
      {list.data && list.data.items.length === 0 && <p className="mt-6 rounded-[6px] border border-dashed border-control px-5 py-8 text-center text-[13px] text-muted">No fact-checks match these filters.</p>}

      {list.data && list.data.items.length > 0 && (
        <div className={`mt-3 rounded-[6px] border border-border bg-surface ${list.loading ? 'opacity-60' : ''}`}>
          <table className="w-full text-[13px]">
            <thead className="hidden md:table-header-group">
              <tr className="text-left text-[12px] text-muted">
                <th className="px-5 py-3 font-normal">Fact-check</th><th className="px-3 py-3 font-normal">Verdict</th>
                <th className="px-3 py-3 font-normal">Language</th><th className="px-3 py-3 font-normal">Category</th>
                <th className="px-5 py-3 text-right font-normal">Published</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((fc) => (
                <tr key={fc.id} className="border-t border-rule align-top first:border-t-0 md:first:border-t">
                  <td className="px-5 py-3.5">
                    <a href={fc.original_url} target="_blank" rel="noreferrer" className="group inline-flex items-start gap-1.5 text-[14px] leading-snug font-medium hover:text-accent-ink">
                      {fc.title}<ExternalLink className="mt-1 size-3 shrink-0 text-muted group-hover:text-accent-ink" aria-label="opens original" />
                    </a>
                    {fc.claim_source === 'claim_field' && fc.claim_text !== fc.title && <p className="mt-1 text-[12px] text-muted">Claim: {fc.claim_text}</p>}
                    <p className="mt-1 text-[12px] text-muted">{fc.source_name}</p>
                    <div className="mt-2 flex flex-wrap gap-2 md:hidden">
                      <Pill tone={verdictTone(fc.verdict)}>{verdictLabel(fc.verdict)}</Pill><Pill>{langName(fc.language)}</Pill>
                      <span className="tnum text-[12px] text-muted">{fmtDate(fc.publication_date)}</span>
                    </div>
                  </td>
                  <td className="hidden px-3 py-3.5 md:table-cell"><Pill tone={verdictTone(fc.verdict)} title={fc.verdict_rule ? `rule ${fc.verdict_rule}: “${fc.verdict_raw}”` : 'no rule matched'}>{verdictLabel(fc.verdict)}</Pill></td>
                  <td className="hidden px-3 py-3.5 text-muted md:table-cell">{langName(fc.language)}</td>
                  <td className="hidden px-3 py-3.5 text-muted md:table-cell" title={fc.category_source === 'keyword_inferred' ? 'inferred from keywords' : 'publisher tag'}>
                    {fc.category ?? '—'}{fc.category_source === 'keyword_inferred' && <span className="text-control"> *</span>}
                  </td>
                  <td className="tnum hidden px-5 py-3.5 text-right whitespace-nowrap text-muted md:table-cell">{fmtDate(fc.publication_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > PAGE_SIZE && (
        <nav aria-label="Pagination" className="tnum mt-4 flex items-center justify-between text-[13px]">
          <button disabled={page <= 1} onClick={() => set('page', String(page - 1))} className="h-[34px] rounded-full border border-control px-4 disabled:opacity-40 hover:border-muted">Previous</button>
          <span className="text-muted">Page {page} of {nf.format(pages)}</span>
          <button disabled={page >= pages} onClick={() => set('page', String(page + 1))} className="h-[34px] rounded-full border border-control px-4 disabled:opacity-40 hover:border-muted">Next</button>
        </nav>
      )}
      <p className="mt-3 text-[12px] text-muted">* category inferred from keywords where the publisher gave no topical tag.</p>
    </div>
  )
}

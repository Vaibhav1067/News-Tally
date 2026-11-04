import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar as RBar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../services/api'
import { useAsync } from '../hooks/useAsync'
import { Bar, ErrorNote, Panel, Spinner, Tabs } from '../components/ui'
import { langName, nf, verdictLabel, verdictTone } from '../utils/format'
import type { Statistics } from '../types/api'

const TONE_FILL = { neg: 'neg', warn: 'warn', pos: 'pos', neu: 'ink' } as const
const VERDICT_ORDER = ['FALSE', 'MISLEADING', 'OUTDATED', 'TRUE', 'UNVERIFIED', 'INSUFFICIENT_EVIDENCE', 'UNPARSED']

function RankedList({ data, render = (k: string) => k, toneOf }: {
  data: Record<string, number>; render?: (k: string) => string; toneOf?: (k: string) => 'accent' | 'neg' | 'warn' | 'pos' | 'ink'
}) {
  const rows = Object.entries(data).sort((a, b) => b[1] - a[1])
  const total = rows.reduce((a, [, v]) => a + v, 0)
  const max = Math.max(...rows.map(([, v]) => v), 1)
  return (
    <ul className="space-y-2.5">
      {rows.map(([k, v]) => (
        <li key={k} className="text-[13px]">
          <div className="flex items-baseline justify-between gap-3">
            <span className="truncate">{render(k)}</span>
            <span className="tnum shrink-0"><span className="text-muted">{((v / total) * 100).toFixed(1)}%</span> <span className="ml-2 inline-block min-w-[3.5ch] text-right">{nf.format(v)}</span></span>
          </div>
          <div className="mt-1"><Bar value={v / max} tone={toneOf ? toneOf(k) : 'accent'} /></div>
        </li>
      ))}
    </ul>
  )
}

function Timeline({ s }: { s: Statistics }) {
  const [range, setRange] = useState<'24' | 'all'>('24')
  const data = useMemo(() => (range === 'all' ? s.timeline : s.timeline.slice(-24)), [s, range])
  return (
    <div>
      <div className="h-[230px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 4, left: -18, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#242831" strokeDasharray="3 3" />
            <XAxis dataKey="month" tick={{ fill: '#8f939b', fontSize: 11 }} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={24} />
            <YAxis tick={{ fill: '#8f939b', fontSize: 11 }} tickLine={false} axisLine={false} allowDecimals={false} />
            <Tooltip cursor={{ fill: '#1c1f26' }} contentStyle={{ background: '#1c1f26', border: '1px solid #3a3f4a', borderRadius: 6, fontSize: 12 }}
              labelStyle={{ color: '#f4f4f2' }} itemStyle={{ color: '#8ab6ec' }} formatter={(v) => [v, 'fact-checks']} />
            <RBar dataKey="count" fill="#4a8ad6" radius={[2, 2, 0, 0]} maxBarSize={22} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <div className="w-40"><Tabs label="Timeline range" value={range} onChange={setRange} options={[{ value: '24', label: '24 months' }, { value: 'all', label: 'All' }]} /></div>
        <span className="text-[12px] text-muted">Monthly count by publication date</span>
      </div>
      <p className="mt-3 text-[12px] leading-relaxed text-muted">The shape reflects collection depth, not publishing volume: the collector fetched the most recent pages of each source's archive, so older months are under-represented.</p>
    </div>
  )
}

export default function Intelligence() {
  const { data: s, error, loading, reload } = useAsync(() => api.statistics(), [])

  const finding = useMemo(() => {
    if (!s) return ''
    const v = s.verdict_distribution
    const parsed = Object.entries(v).filter(([k]) => k !== 'UNPARSED').reduce((a, [, n]) => a + n, 0)
    const fm = (v.FALSE ?? 0) + (v.MISLEADING ?? 0) + (v.OUTDATED ?? 0)
    return `${((fm / parsed) * 100).toFixed(1)}% of parsed verdicts are FALSE, MISLEADING or OUTDATED; only ${v.TRUE ?? 0} are TRUE — fact-checkers mostly publish debunks, which is why the classifier cannot learn what a true claim looks like.`
  }, [s])

  return (
    <div className="mx-auto max-w-[1320px] px-5 pt-8 md:px-8">
      <h1 className="text-[26px] font-bold tracking-[-0.015em]">Dataset intelligence</h1>
      <p className="mt-1 text-[14px] text-muted">Live statistics of the collected fact-check dataset{s?.date_range[0] ? `, ${s.date_range[0]} to ${s.date_range[1]}` : ''}.</p>

      {error && <div className="mt-6"><ErrorNote message={error} onRetry={reload} /></div>}
      {loading && <Spinner label="Computing statistics" />}
      {s && (
        <>
          <p className="mt-4 max-w-[90ch] rounded-[6px] bg-warn-bg px-4 py-3 text-[13px] leading-relaxed text-warn-ink">{s.note}</p>

          <dl className="mt-6 grid grid-cols-2 divide-rule rounded-[6px] border border-border bg-surface md:grid-cols-5 md:divide-x">
            {[
              ['Fact-checks', nf.format(s.total_fact_checks)],
              ['Languages', String(Object.keys(s.language_distribution).length)],
              ['Publishers', String(Object.keys(s.source_distribution).length)],
              ['Duplicates removed', `${s.data_quality.duplicate_pct ?? '—'}%`],
              ['Analyses run here', nf.format(s.analyses_run)],
            ].map(([k, v]) => (
              <div key={k} className="px-5 py-4"><dt className="text-[12px] text-muted">{k}</dt><dd className="tnum mt-1 text-[24px] font-semibold">{v}</dd></div>
            ))}
          </dl>
          <p className="mt-3 text-[13px] text-ink">{finding}</p>

          <div className="mt-6 grid gap-6 lg:grid-cols-[43fr_57fr]">
            <Panel title="Verdict distribution" aside="normalised from publisher wording">
              <RankedList data={Object.fromEntries(VERDICT_ORDER.filter((k) => s.verdict_distribution[k]).map((k) => [k, s.verdict_distribution[k]]))}
                render={verdictLabel} toneOf={(k) => TONE_FILL[verdictTone(k)]} />
              <Link to="/explorer?verdict=UNPARSED" className="mt-4 inline-block text-[12px] text-muted underline underline-offset-2 hover:text-ink">Browse the unparsed records</Link>
            </Panel>
            <Panel title="Publication timeline"><Timeline s={s} /></Panel>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <Panel title="Languages"><RankedList data={s.language_distribution} render={langName} /></Panel>
            <Panel title="Sources"><RankedList data={s.source_distribution} /></Panel>
            <Panel title="Top categories" aside="publisher tags + keyword inference"><RankedList data={s.category_distribution} /></Panel>
          </div>

          <h2 className="mt-10 text-[20px] text-muted">Verdicts by language</h2>
          <div className="mt-3 overflow-x-auto rounded-[6px] border border-border bg-surface">
            <table className="w-full min-w-[640px] text-[13px]">
              <thead><tr className="text-[12px] text-muted"><th className="px-5 py-3 text-left font-normal">Language</th>
                {VERDICT_ORDER.map((v) => <th key={v} className="px-3 py-3 text-right font-normal">{verdictLabel(v)}</th>)}
                <th className="px-5 py-3 text-right font-normal">Total</th></tr></thead>
              <tbody>
                {Object.entries(s.language_by_verdict).map(([lang, row]) => {
                  const total = Object.values(row).reduce((a, b) => a + b, 0)
                  return (
                    <tr key={lang} className="border-t border-rule">
                      <td className="px-5 py-2.5 font-medium">{langName(lang)}</td>
                      {VERDICT_ORDER.map((v) => <td key={v} className={`tnum px-3 py-2.5 text-right ${row[v] ? '' : 'text-muted'}`}>{row[v] ? nf.format(row[v]) : '—'}</td>)}
                      <td className="tnum px-5 py-2.5 text-right font-semibold">{nf.format(total)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <h2 className="mt-10 text-[20px] text-muted">Data quality</h2>
          <div className="mt-3 grid gap-6 lg:grid-cols-2">
            <Panel title="Pipeline counts" aside={s.data_quality.built_at ? `built ${s.data_quality.built_at.slice(0, 10)}` : undefined}>
              <dl className="divide-y divide-rule">
                {[['Raw records collected', s.data_quality.raw_rows], ['Failed validation', s.data_quality.invalid_rows],
                  ['Exact duplicates removed', (s.data_quality.raw_rows ?? 0) - (s.data_quality.invalid_rows ?? 0) - (s.data_quality.final_rows ?? 0)],
                  ['Rows in near-duplicate groups', s.data_quality.near_duplicate_rows], ['Final records', s.data_quality.final_rows]]
                  .map(([k, v]) => <div key={String(k)} className="flex justify-between py-2 text-[13px]"><dt className="text-muted">{k}</dt><dd className="tnum">{v == null ? '—' : nf.format(Number(v))}</dd></div>)}
              </dl>
            </Panel>
            <Panel title="Missing values" aside="% of final records">
              <dl className="divide-y divide-rule">
                {Object.entries(s.data_quality.missing_pct_processed ?? {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                  <div key={k} className="flex justify-between py-2 text-[13px]"><dt className="text-muted">{k.replace(/_/g, ' ')}</dt><dd className="tnum">{v.toFixed(1)}%</dd></div>
                ))}
              </dl>
            </Panel>
          </div>
        </>
      )}
    </div>
  )
}

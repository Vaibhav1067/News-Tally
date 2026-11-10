import { Link, useNavigate } from 'react-router-dom'
import { ClaimInput, EXAMPLES } from '../components/ClaimInput'
import { RiskSummary } from '../components/analysis/RiskSummary'
import { MatchList } from '../components/analysis/MatchList'
import { Panel, Pill } from '../components/ui'
import { api } from '../services/api'
import { useAsync } from '../hooks/useAsync'
import india from '@svg-maps/india'
import { fmtDate, langName, nf, verdictLabel, verdictTone } from '../utils/format'
import { fillFor, rate1 } from '../utils/mapScale'

const STEPS = [
  ['Reads the text', 'Pasted text, or the readable body of a news link. Links to private networks are refused.'],
  ['Detects the language', 'English, Hindi, Kannada, mixed text and romanised Hindi, from the Unicode scripts.'],
  ['Searches the fact-checks', 'Meaning-based and character-level matching against every collected fact-check.'],
  ['Runs a classifier', 'Reports which verdict fact-checkers gave to claims worded like this one.'],
  ['Looks up the source', 'What the dataset records about the outlet. No credibility score is computed.'],
  ['Explains itself', 'Which words moved the model, how the risk index adds up, and what evidence is missing.'],
]

const OUTCOMES = [
  ['High misinformation risk', 'A closely matching claim was rated false by a fact-checker.', 'neg'],
  ['Potentially misleading', 'Matching fact-checks found it misleading, miscaptioned or outdated.', 'warn'],
  ['Evidence supports claim', 'A matching fact-check confirmed it.', 'pos'],
  ['Unverified', 'No close fact-check exists. Not true, not false: unchecked.', 'neu'],
  ['Insufficient evidence', 'Too short, or in a language the models were not trained on.', 'neu'],
] as const

const H2 = 'font-serif text-[22px] leading-tight font-semibold tracking-[-0.01em]'
const LINK = 'text-[14px] font-medium text-ink underline underline-offset-2'

export default function Landing() {
  const nav = useNavigate()
  const stats = useAsync(() => api.statistics(), [])
  const latest = useAsync(() => api.factChecks({ page_size: 6 }), [])
  // A real analysis, computed live on every visit (nothing is stored).
  const example = useAsync(() => api.analyze({ text: EXAMPLES[0].text }), [])
  const map = useAsync(() => api.indiaMap(), [])
  const s = stats.data
  const total = s ? nf.format(s.total_fact_checks) : 'the collected'

  return (
    <div className="mx-auto max-w-[1160px] px-5 pt-9 md:px-8">
      <h1 className="font-serif text-[26px] leading-[1.15] font-semibold tracking-[-0.015em] md:text-[32px]">Has this claim already been fact-checked?</h1>
      <p className="mt-2 max-w-[70ch] text-[15px] text-muted">Paste a forward, a post or a news link. News Tally searches {total} fact-checks published by Factly and Alt News and shows what they found.</p>

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1.25fr_1fr]">
        <div>
          <ClaimInput rows={13} onSubmit={(input) => nav('/analyze', { state: { input } })} />
          <div className="mt-4 flex flex-wrap items-center gap-2 text-[13px]">
            <span className="text-muted">Try:</span>
            {EXAMPLES.map((ex) => (
              <button key={ex.label} type="button" onClick={() => nav('/analyze', { state: { input: { text: ex.text } } })}
                className="h-[30px] rounded-ctl border border-control bg-surface px-3 text-ink transition hover:border-muted">{ex.label}</button>
            ))}
          </div>
          <p className="mt-4 text-[13px] text-muted">Your text is not stored unless you tick “Save to history”.</p>
        </div>

        <Panel title="Latest fact-checks" aside={<Link to="/explorer" className="font-medium text-ink underline underline-offset-2">View all {s ? nf.format(s.total_fact_checks) : ''}</Link>}>
          <ul className="divide-y divide-rule">
            {latest.data?.items.map((fc) => (
              <li key={fc.id} className="py-2.5 first:pt-0 last:pb-0">
                <a href={fc.original_url} target="_blank" rel="noreferrer" className="line-clamp-2 font-serif text-[15px] leading-snug font-semibold hover:underline">{fc.title}</a>
                <div className="mt-1 flex items-center gap-2 text-[12px] text-muted">
                  <Pill tone={verdictTone(fc.verdict)}>{verdictLabel(fc.verdict)}</Pill>
                  <span className="truncate">{fc.source_name} · {langName(fc.language)} · {fmtDate(fc.publication_date)}</span>
                </div>
              </li>
            ))}
            {latest.error && <li className="py-4 text-[13px] text-muted">Couldn't load the latest fact-checks: the API is not reachable.</li>}
            {latest.loading && <li className="py-4 text-[13px] text-muted">Loading the latest fact-checks…</li>}
          </ul>
        </Panel>
      </div>

      {/* Worked example, run live */}
      <section aria-labelledby="ex-h" className="mt-14">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <h2 id="ex-h" className={H2}>What a result looks like</h2>
          <button onClick={() => nav('/analyze', { state: { input: { text: EXAMPLES[0].text } } })} className={LINK}>Open the full analysis</button>
        </div>
        <p className="mt-2 max-w-[80ch] text-[14px] text-muted">The claim “{EXAMPLES[0].text}”, analysed by the API when this page loaded.</p>
        <div className="mt-4 grid items-start gap-6 lg:grid-cols-[1.25fr_1fr]">
          {example.data ? (
            <>
              <RiskSummary r={example.data} embedded />
              <Panel title="Top matching fact-checks">
                <MatchList matches={example.data.matching_fact_checks.slice(0, 2)} backend={example.data.retrieval_backend} />
              </Panel>
            </>
          ) : (
            <p className="rounded-card border border-dashed border-control px-5 py-8 text-[13px] text-muted lg:col-span-2">{example.error ? 'Couldn\'t run the example: the API is not reachable.' : 'Running the example…'}</p>
          )}
        </div>
      </section>

      {/* Claims by place */}
      {map.data && (() => {
        const m = map.data
        const by = Object.fromEntries(m.states.map((x) => [x.code, x]))
        const top = [...m.states].sort((a, b) => b.mentions - a.mentions).slice(0, 6)
        return (
          <section aria-labelledby="map-h" className="mt-14">
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
              <h2 id="map-h" className={H2}>Where the claims are about</h2>
              <Link to="/map" className={LINK}>Open the India map</Link>
            </div>
            <p className="mt-2 max-w-[80ch] text-[14px] text-muted">{nf.format(m.fact_checks_located)} of {nf.format(m.fact_checks_total)} fact-checks name a state. The map shades each state by its registered crime rate in 2023.</p>
            <div className="mt-4 grid items-center gap-6 rounded-card border border-border bg-surface p-5 md:grid-cols-[300px_1fr] md:gap-10">
              <Link to="/map" aria-label="Open the India map">
                <svg viewBox={india.viewBox} className="mx-auto block h-auto w-full max-w-[300px]" role="img" aria-label="India shaded by registered crime rate">
                  {india.locations.map((l) => <path key={l.id} d={l.path} fill={by[m.map_regions[l.id]] ? fillFor(by[m.map_regions[l.id]].crime_rate) : '#ecece8'} stroke="#ffffff" strokeWidth={0.8} />)}
                </svg>
              </Link>
              <table className="w-full text-[14px]">
                <caption className="pb-2 text-left text-[13px] font-semibold">States named most in fact-checked claims</caption>
                <thead><tr className="text-[12px] text-muted"><th className="py-2 text-left font-normal">State</th><th className="py-2 text-right font-normal">Claims fact-checked</th><th className="py-2 text-right font-normal">Crimes per lakh</th></tr></thead>
                <tbody>
                  {top.map((x) => (
                    <tr key={x.code} className="border-t border-rule">
                      <th scope="row" className="py-2 text-left font-medium">{x.name}</th>
                      <td className="tnum py-2 text-right">{nf.format(x.mentions)}</td>
                      <td className="tnum py-2 text-right"><span className="mr-2 inline-block size-2.5 rounded-[2px] align-baseline" style={{ background: fillFor(x.crime_rate) }} />{rate1.format(x.crime_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )
      })()}

      {/* Reference: steps, outcomes, coverage */}
      <div className="mt-14 grid gap-x-10 gap-y-12 lg:grid-cols-3">
        <section aria-labelledby="how-h">
          <h2 id="how-h" className={H2}>What happens to your text</h2>
          <ol className="mt-4 space-y-3.5 text-[14px]">
            {STEPS.map(([h, d]) => (
              <li key={h}><span className="font-semibold">{h}.</span> <span className="text-muted">{d}</span></li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="out-h">
          <h2 id="out-h" className={H2}>The five possible answers</h2>
          <dl className="mt-4 space-y-3.5 text-[14px]">
            {OUTCOMES.map(([h, d, tone]) => (
              <div key={h}>
                <dt><Pill tone={tone}>{h}</Pill></dt>
                <dd className="mt-1.5 text-muted">{d}</dd>
              </div>
            ))}
          </dl>
          <Link to="/methodology#risk" className={`mt-4 inline-block ${LINK}`}>How the risk index is calculated</Link>
        </section>

        <section aria-labelledby="cov-h">
          <h2 id="cov-h" className={H2}>What it covers</h2>
          <table className="mt-4 w-full text-[14px]">
            <caption className="sr-only">Fact-checks by language and by source</caption>
            <tbody>
              {s && Object.entries(s.language_distribution).map(([k, v]) => (
                <tr key={k} className="border-b border-border"><th scope="row" className="py-2 text-left font-normal">{langName(k)}</th><td className="tnum py-2 text-right">{nf.format(v)}</td></tr>
              ))}
              {s && Object.entries(s.source_distribution).map(([k, v]) => (
                <tr key={k} className="border-b border-border"><th scope="row" className="py-2 text-left font-normal">{k}</th><td className="tnum py-2 text-right">{nf.format(v)}</td></tr>
              ))}
              <tr className="border-b border-border"><th scope="row" className="py-2 text-left font-normal">BOOM Live</th><td className="py-2 text-right text-muted">refused access</td></tr>
              <tr><th scope="row" className="py-2 text-left font-normal">PIB Fact Check</th><td className="py-2 text-right text-muted">refused access</td></tr>
            </tbody>
          </table>
          <p className="mt-3 text-[13px] text-muted">Counts are fact-checks in the dataset. Collected only from public APIs that robots.txt allows; sources that refused were not bypassed.</p>
        </section>
      </div>

      {/* Limits */}
      <section aria-labelledby="disc-h" className="mt-14 grid items-start gap-6 lg:grid-cols-[1fr_1.25fr]">
        <figure>
          <img src="/images/kolkata-street-reading.jpg" alt="A man reads a newspaper at a busy crossing in Manicktala, Kolkata, as a yellow taxi passes"
            className="aspect-[3/2] w-full rounded-card object-cover object-[50%_60%]" />
          <figcaption className="mt-2 text-[12px] text-muted">The morning paper at Manicktala crossing, Kolkata.</figcaption>
        </figure>
        <div className="max-w-[62ch] text-[15px] leading-relaxed">
          <h2 id="disc-h" className={H2}>What this tool cannot tell you</h2>
          <p className="mt-4">It does not decide what is true. It finds what professional fact-checkers have published, shows how a model reads the text, and lists what it could not check. Open the original fact-check before you share a conclusion.</p>
          <p className="mt-3">The dataset reflects what two newsrooms chose to investigate. It does not measure misinformation across India, and it says nothing about the communities or parties named in the claims it contains.</p>
          <Link to="/methodology" className={`mt-4 inline-block ${LINK}`}>Read the methodology and limitations</Link>
        </div>
      </section>
    </div>
  )
}

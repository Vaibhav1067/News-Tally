import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, ExternalLink } from 'lucide-react'
import { ClaimInput, EXAMPLES } from '../components/ClaimInput'
import { RiskSummary } from '../components/analysis/RiskSummary'
import { MatchList } from '../components/analysis/MatchList'
import { Pill } from '../components/ui'
import { api } from '../services/api'
import { useAsync } from '../hooks/useAsync'
import { fmtDate, langName, nf, verdictLabel, verdictTone } from '../utils/format'

const inView = { initial: { opacity: 0, y: 22 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: '-60px' } }
const t = (i: number) => ({ duration: 0.45, delay: i * 0.08, ease: [0.2, 0.7, 0.2, 1] as const })

const PIPELINE = [
  ['Extract', 'Takes pasted text, or the readable body of a news link. Links to private networks are refused.'],
  ['Detect language', 'Reads the Unicode scripts: English, Hindi, Kannada, mixed text and romanised Hindi.'],
  ['Retrieve fact-checks', 'Searches every collected Indian fact-check with meaning-based and character-level matching.'],
  ['Classify', 'Reports which verdict fact-checkers gave to claims worded like this one.'],
  ['Profile the source', 'Shows what the dataset records about the outlet. It never computes a credibility score.'],
  ['Explain and assess', 'Shows which words moved the model, a documented risk index, and the evidence that is missing.'],
]

const OUTCOMES = [
  ['High misinformation risk', 'A closely matching claim was rated false by a fact-checker.', 'neg'],
  ['Potentially misleading', 'Matching fact-checks found it misleading, miscaptioned or outdated.', 'warn'],
  ['Evidence supports claim', 'A matching fact-check confirmed it.', 'pos'],
  ['Unverified', 'No close fact-check exists. Not true, not false: unchecked.', 'neu'],
  ['Insufficient evidence', 'Too short, or in a language the models were not trained on.', 'neu'],
] as const

const TONE_INK = { neg: 'text-neg-ink', warn: 'text-warn-ink', pos: 'text-pos-ink', neu: 'text-ink' } as const
const H2 = 'text-[30px] leading-[1.08] font-bold tracking-[-0.025em] md:text-[44px]'

export default function Landing() {
  const nav = useNavigate()
  const stats = useAsync(() => api.statistics(), [])
  const latest = useAsync(() => api.factChecks({ page_size: 5 }), [])
  // A real analysis, computed live on every visit (nothing is stored).
  const example = useAsync(() => api.analyze({ text: EXAMPLES[0].text }), [])
  const s = stats.data
  const total = s ? nf.format(s.total_fact_checks) : '…'

  return (
    <div className="text-[16px]">
      {/* Hero */}
      <section className="mx-auto grid max-w-[1320px] gap-10 px-5 pt-12 pb-16 md:px-8 lg:grid-cols-[1.15fr_1fr] lg:pt-20">
        <div>
          <motion.h1 initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={t(0)}
            className="max-w-[14ch] text-[31px] leading-[1.04] font-bold tracking-[-0.035em] sm:text-[56px] lg:text-[76px]">
            Before you believe it, investigate it.
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={t(1)} className="mt-6 max-w-[46ch] text-[18px] leading-relaxed">
            AI-powered misinformation intelligence built for India's diverse information ecosystem. Paste a forward, a post or a news link and see the published fact-checks behind it.
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={t(2)} className="mt-8">
            <ClaimInput compact onSubmit={(input) => nav('/analyze', { state: { input } })} />
          </motion.div>
          <p className="mt-4 text-[14px] text-muted">Searches {total} fact-checks by Factly and Alt News. Your text is not stored unless you choose to save it.</p>
        </div>

        <motion.aside initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={t(2)} data-ui
          aria-labelledby="latest-h" className="self-start rounded-[6px] border border-border bg-surface">
          <header className="flex items-baseline justify-between px-5 pt-4 pb-2">
            <h2 id="latest-h" className="text-[15px] font-semibold">Latest fact-checks in the dataset</h2>
            <Link to="/explorer" className="text-[13px] text-muted hover:text-ink">View all</Link>
          </header>
          <ul className="divide-y divide-rule px-5 pb-2">
            {latest.data?.items.map((fc) => (
              <li key={fc.id} className="py-3">
                <div className="flex items-center gap-2 text-[13px] text-muted">
                  <Pill tone={verdictTone(fc.verdict)}>{verdictLabel(fc.verdict)}</Pill>
                  <span className="truncate">{fc.source_name} · {langName(fc.language)} · {fmtDate(fc.publication_date)}</span>
                </div>
                <a href={fc.original_url} target="_blank" rel="noreferrer" className="group mt-1.5 flex items-start gap-1.5 text-[14px] leading-snug hover:text-accent-ink">
                  <span className="line-clamp-2">{fc.title}</span><ExternalLink className="mt-1 size-3 shrink-0 text-muted" aria-label="opens original" />
                </a>
              </li>
            ))}
            {latest.error && <li className="py-6 text-[14px] text-muted">The API is not reachable, so the live feed cannot load. Start the backend to see it.</li>}
            {latest.loading && <li className="py-6 text-[14px] text-muted">Loading the latest fact-checks…</li>}
          </ul>
        </motion.aside>
      </section>

      {/* Photo band */}
      <motion.figure {...inView} transition={t(0)} className="mx-auto max-w-[1320px] px-5 md:px-8">
        <div className="overflow-hidden rounded-[6px]">
          <motion.img initial={{ scale: 1.06 }} whileInView={{ scale: 1 }} viewport={{ once: true }} transition={{ duration: 1.4, ease: [0.2, 0.7, 0.2, 1] }}
            src="/images/kolkata-street-reading.jpg" alt="A man reads a newspaper at a busy crossing in Manicktala, Kolkata, as a yellow taxi passes"
            className="aspect-[21/9] w-full object-cover object-[50%_60%]" />
        </div>
        <figcaption className="mt-2 text-[13px] text-muted">The morning paper at Manicktala crossing, Kolkata. Most claims now reach readers through a phone instead.</figcaption>
      </motion.figure>

      {/* How it works */}
      <section aria-labelledby="how-h" className="mx-auto grid max-w-[1320px] gap-12 px-5 pt-28 md:px-8 lg:grid-cols-[1fr_1.25fr]">
        <div>
          <motion.h2 {...inView} transition={t(0)} id="how-h" className={`max-w-[16ch] ${H2}`}>Six checks before a verdict.</motion.h2>
          <motion.p {...inView} transition={t(1)} className="mt-5 max-w-[46ch] leading-relaxed">Each stage is its own tested Python module. Every analysis runs all six and shows its working, including what it could not check.</motion.p>
          <motion.img {...inView} transition={t(2)} src="/images/newspaper-vendor.jpg" alt="A newspaper vendor in a mask and gloves delivers bundled papers by motorcycle"
            className="mt-8 aspect-[4/3] w-full max-w-[520px] rounded-[6px] object-cover" />
          <p className="mt-2 text-[13px] text-muted">A vendor wraps up the day's deliveries.</p>
        </div>
        <dl className="grid content-start gap-x-10 gap-y-9 sm:grid-cols-2">
          {PIPELINE.map(([h, d], i) => (
            <motion.div key={h} {...inView} transition={t(i % 2)}>
              <dt className="text-[20px] font-semibold tracking-[-0.01em]">{h}</dt>
              <dd className="mt-2 leading-relaxed">{d}</dd>
            </motion.div>
          ))}
        </dl>
      </section>

      {/* Live worked example */}
      <section aria-labelledby="ex-h" className="mt-28 bg-surface">
        <div className="mx-auto max-w-[1320px] px-5 py-24 md:px-8">
          <div className="grid gap-6 lg:grid-cols-[1fr_1.25fr]">
            <motion.h2 {...inView} transition={t(0)} id="ex-h" className={`max-w-[17ch] ${H2}`}>A real analysis, run as this page loaded.</motion.h2>
            <motion.div {...inView} transition={t(1)}>
              <p className="max-w-[56ch] leading-relaxed">The claim: “{EXAMPLES[0].text}.” Nothing below is a mock-up. It is the API's live answer.</p>
              <button onClick={() => nav('/analyze', { state: { input: { text: EXAMPLES[0].text } } })}
                className="mt-4 inline-flex items-center gap-2 text-[15px] font-semibold text-accent-ink hover:text-ink">Open the full analysis <ArrowRight className="size-4" /></button>
            </motion.div>
          </div>
          <motion.div {...inView} transition={t(2)} className="mt-10 grid gap-6 lg:grid-cols-[1.25fr_1fr]">
            {example.data ? (
              <>
                <RiskSummary r={example.data} embedded />
                <div>
                  <h3 className="mb-3 text-[18px] font-semibold">Top matching fact-checks</h3>
                  <div data-ui className="rounded-[6px] border border-border bg-ground p-5"><MatchList matches={example.data.matching_fact_checks.slice(0, 2)} backend={example.data.retrieval_backend} /></div>
                </div>
              </>
            ) : (
              <p className="text-[14px] text-muted">{example.error ? 'The API is not reachable, so the live example cannot run.' : 'Running the example…'}</p>
            )}
          </motion.div>
        </div>
      </section>

      {/* Outcomes */}
      <section aria-labelledby="out-h" className="mx-auto grid max-w-[1320px] gap-12 px-5 pt-28 md:px-8 lg:grid-cols-[1fr_1.25fr]">
        <div>
          <motion.h2 {...inView} transition={t(0)} id="out-h" className={`max-w-[15ch] ${H2}`}>Five honest answers, not true or false.</motion.h2>
          <motion.p {...inView} transition={t(1)} className="mt-5 max-w-[46ch] leading-relaxed">A classifier predicting “fake” is not proof. NEWS TALLY reports high risk only when a published fact-check closely matches the claim, and says plainly when nothing does.</motion.p>
          <Link to="/methodology#risk" className="mt-6 inline-flex items-center gap-2 text-[15px] font-semibold text-accent-ink hover:text-ink">How the risk index is calculated <ArrowRight className="size-4" /></Link>
        </div>
        <dl className="space-y-7">
          {OUTCOMES.map(([h, d, tone], i) => (
            <motion.div key={h} {...inView} transition={t(i)} className="grid gap-2 sm:grid-cols-[230px_1fr] sm:gap-6">
              <dt className={`text-[17px] font-semibold ${TONE_INK[tone]}`}>{h}</dt>
              <dd className="leading-relaxed">{d}</dd>
            </motion.div>
          ))}
        </dl>
      </section>

      {/* Coverage */}
      <section aria-labelledby="cov-h" className="mx-auto max-w-[1320px] px-5 pt-28 md:px-8">
        <motion.h2 {...inView} transition={t(0)} id="cov-h" className={`max-w-[22ch] ${H2}`}>Three languages, two newsrooms.</motion.h2>
        <div className="mt-12 grid gap-10 lg:grid-cols-3">
          <motion.div {...inView} transition={t(0)}>
            <h3 className="text-[20px] font-semibold">Supported languages</h3>
            <dl className="mt-4 space-y-2.5">
              {s && Object.entries(s.language_distribution).map(([k, v]) => (
                <div key={k} className="flex justify-between"><dt>{langName(k)}</dt><dd className="tnum text-muted">{nf.format(v)} fact-checks</dd></div>
              ))}
            </dl>
            <p className="mt-4 leading-relaxed">Mixed Hindi–English text is detected and analysed. Other Indian languages are detected and marked as outside the training data.</p>
          </motion.div>
          <motion.div {...inView} transition={t(1)}>
            <h3 className="text-[20px] font-semibold">Data sources</h3>
            <dl className="mt-4 space-y-2.5">
              {s && Object.entries(s.source_distribution).map(([k, v]) => (
                <div key={k} className="flex justify-between"><dt>{k}</dt><dd className="tnum text-muted">{nf.format(v)} collected</dd></div>
              ))}
              <div className="flex justify-between"><dt>BOOM Live</dt><dd className="text-muted">refused access</dd></div>
              <div className="flex justify-between"><dt>PIB Fact Check</dt><dd className="text-muted">refused access</dd></div>
            </dl>
            <p className="mt-4 leading-relaxed">Collected only from public APIs that robots.txt allows. Sources that refused access were not bypassed.</p>
          </motion.div>
          <motion.figure {...inView} transition={t(2)}>
            <img src="/images/assam-tribune.jpg" alt="The Assam Tribune and Dainik Asam building in Guwahati, lit up at night" className="aspect-[4/3] w-full rounded-[6px] object-cover" />
            <figcaption className="mt-2 text-[13px] text-muted">The Assam Tribune building, Guwahati. India's regional press publishes in dozens of languages; this dataset covers three.</figcaption>
          </motion.figure>
        </div>
      </section>

      {/* Disclaimer */}
      <section aria-labelledby="disc-h" className="mx-auto grid max-w-[1320px] gap-8 px-5 pt-28 md:px-8 lg:grid-cols-[1fr_1.25fr]">
        <motion.h2 {...inView} transition={t(0)} id="disc-h" className={H2}>An assistant, not a censor.</motion.h2>
        <motion.div {...inView} transition={t(1)} className="max-w-[62ch] space-y-4 leading-relaxed">
          <p>NEWS TALLY does not decide what is true. It finds what professional fact-checkers have published, shows how a model reads the text, and lists what it could not check. Always open the original fact-check before you share a conclusion.</p>
          <p>The dataset reflects what two newsrooms chose to investigate. It does not measure misinformation across India, and it says nothing about the communities or parties named in the claims it contains.</p>
          <Link to="/analyze" className="inline-flex h-[42px] items-center gap-2 rounded-full bg-[#2f6db5] px-5 text-[15px] font-semibold text-white transition hover:bg-[#3b7cc6] active:scale-[0.98]">Analyze a claim <ArrowRight className="size-4" /></Link>
        </motion.div>
      </section>
    </div>
  )
}

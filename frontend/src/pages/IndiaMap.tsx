import { memo, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState, type RefObject } from 'react'
import { Link } from 'react-router-dom'
import india from '@svg-maps/india'
import { api } from '../services/api'
import { useAsync } from '../hooks/useAsync'
import { ErrorNote, Pill, Spinner, Tabs } from '../components/ui'
import { fmtDate, nf, verdictLabel, verdictTone } from '../utils/format'
import type { IndiaMapData, MapState } from '../types/api'
import { BINS, CLAIM_BINS, claimFill, fillFor, rate1 } from '../utils/mapScale'

const H2 = 'font-serif text-[22px] leading-tight font-semibold tracking-[-0.01em]'
type Mode = 'crime' | 'claims'
// Territories too small to point at on the map; they get their own buttons under it.
const SMALL = ['dl', 'ch', 'py', 'ga', 'sk', 'ld', 'an', 'dnd', 'la']
const regionsOf = (code?: string | null) => (code === 'la' ? ['jk'] : code === 'dnd' ? ['dn', 'dd'] : code ? [code] : [])

/* The 36 shapes. Memoised: hovering never re-renders them, so the heavy path data is laid out once.
   The dimming of the other states on hover is pure CSS (see .india-states in index.css). */
const Shapes = memo(function Shapes({ fills, labels, onEnter, onLeave, onPick }: {
  fills: Record<string, string>; labels: Record<string, string>
  onEnter: (id: string) => void; onLeave: () => void; onPick: (id: string) => void
}) {
  return (
    <g className="india-states">
      {india.locations.map((l) => (
        <path key={l.id} d={l.path} fill={fills[l.id] ?? '#ecece8'} stroke="#ffffff" strokeWidth={0.9} strokeLinejoin="round"
          tabIndex={0} aria-label={labels[l.id] ?? l.name}
          onPointerEnter={() => onEnter(l.id)} onPointerLeave={onLeave} onFocus={() => onEnter(l.id)} onBlur={onLeave}
          onClick={() => onPick(l.id)} />
      ))}
    </g>
  )
})

const StateTable = memo(function StateTable({ data, mode, activeCode, onHover, onPick }: {
  data: IndiaMapData; mode: Mode; activeCode?: string; onHover: (code: string | null) => void; onPick: (code: string) => void
}) {
  const rows = useMemo(() => [...data.states].sort((a, b) => mode === 'crime' ? a.rate_rank - b.rate_rank : b.mentions - a.mentions || a.rate_rank - b.rate_rank), [data, mode])
  const maxRate = Math.max(1, ...data.states.map((s) => s.crime_rate))
  const maxMentions = Math.max(1, ...data.states.map((s) => s.mentions))
  return (
    <div className="mt-3 overflow-x-auto rounded-card border border-border bg-surface">
      <table className="w-full min-w-[680px] text-[13px]">
        <thead>
          <tr className="text-[12px] text-muted">
            <th className="py-3 pr-2 pl-5 text-right font-normal">Rank</th><th className="px-3 py-3 text-left font-normal">State or territory</th>
            <th className="w-[24%] px-3 py-3 text-left font-normal">Crimes per lakh</th><th className="px-3 py-3 text-right font-normal">Registered crimes</th>
            <th className="w-[20%] px-3 py-3 text-left font-normal">Claims fact-checked</th><th className="py-3 pr-5 pl-3 text-right font-normal">Rated false</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.code} onPointerEnter={() => onHover(s.code)} onPointerLeave={() => onHover(null)} onClick={() => onPick(s.code)}
              className={`cursor-pointer border-t border-rule transition-colors duration-150 ${activeCode === s.code ? 'bg-raised' : ''}`}>
              <td className="tnum py-2.5 pr-2 pl-5 text-right text-muted">{s.rate_rank}</td>
              <td className="px-3 py-2.5 font-medium">{s.name}</td>
              <td className="px-3 py-2.5">
                <div className="flex items-center gap-3">
                  <span className="tnum w-[58px] shrink-0 text-right">{rate1.format(s.crime_rate)}</span>
                  <span className="h-2 flex-1"><span className="block h-2 rounded-[2px]" style={{ width: `${(s.crime_rate / maxRate) * 100}%`, background: fillFor(s.crime_rate) }} /></span>
                </div>
              </td>
              <td className="tnum px-3 py-2.5 text-right">{nf.format(s.total_crimes)}</td>
              <td className="px-3 py-2.5">
                <div className="flex items-center gap-3">
                  <span className={`tnum w-[34px] shrink-0 text-right ${s.mentions ? '' : 'text-muted'}`}>{nf.format(s.mentions)}</span>
                  <span className="h-2 flex-1">{s.mentions > 0 && <span className="block h-2 rounded-[2px]" style={{ width: `${(s.mentions / maxMentions) * 100}%`, background: claimFill(s.mentions) }} />}</span>
                </div>
              </td>
              <td className={`tnum py-2.5 pr-5 pl-3 text-right ${s.false_mentions ? '' : 'text-muted'}`}>{s.mentions ? nf.format(s.false_mentions) : '—'}</td>
            </tr>
          ))}
          <tr className="border-t border-border font-semibold">
            <td /><td className="px-3 py-2.5">India</td>
            <td className="px-3 py-2.5"><span className="tnum inline-block w-[58px] text-right">{rate1.format(data.crime_source.national_rate)}</span></td>
            <td className="tnum px-3 py-2.5 text-right">{nf.format(data.crime_source.national_total)}</td>
            <td className="px-3 py-2.5"><span className="tnum inline-block w-[34px] text-right">{nf.format(data.fact_checks_located)}</span></td><td />
          </tr>
        </tbody>
      </table>
    </div>
  )
})

type CardHandle = { show: (code: string) => void; hide: () => void; el: () => HTMLDivElement | null }

/* The card that follows the pointer. It owns its own state, so showing a state re-renders only this
   small component; its position is written straight to the DOM by the page. */
function HoverCard({ handle, byCode, count }: { handle: RefObject<CardHandle | null>; byCode: Record<string, MapState>; count: number }) {
  const [code, setCode] = useState<string | null>(null)
  const el = useRef<HTMLDivElement>(null)
  useImperativeHandle(handle, () => ({
    show: (c) => { setCode(c); if (el.current) el.current.dataset.on = '1' },
    hide: () => { if (el.current) delete el.current.dataset.on },
    el: () => el.current,
  }), [])
  const s = code ? byCode[code] : undefined
  const dot = (v: string | null) => ({ neg: 'bg-negative', warn: 'bg-warning', pos: 'bg-positive', neu: 'bg-control' })[verdictTone(v)]
  return (
    <div ref={el} aria-hidden className="map-card pointer-events-none absolute top-0 left-0 z-20 w-[292px]">
      <div className="rounded-card border border-control bg-surface p-3.5">
        {s && (
          <>
            <div className="font-serif text-[17px] leading-tight font-semibold">{s.name}</div>
            <div className="tnum mt-2 flex items-center gap-2 text-[13px]">
              <span className="size-2.5 shrink-0 rounded-[2px]" style={{ background: fillFor(s.crime_rate) }} />
              <span><span className="font-semibold">{rate1.format(s.crime_rate)}</span> crimes per lakh <span className="text-muted">· rank {s.rate_rank} of {count}</span></span>
            </div>
            <div className="tnum mt-1 flex items-center gap-2 text-[13px]">
              <span className="size-2.5 shrink-0 rounded-[2px]" style={{ background: claimFill(s.mentions) }} />
              <span><span className="font-semibold">{nf.format(s.mentions)}</span> claims fact-checked{s.mentions > 0 && <span className="text-muted"> · {nf.format(s.false_mentions)} false</span>}</span>
            </div>
            {s.recent.length > 0 && (
              <ul className="mt-3 space-y-2 border-t border-rule pt-3">
                {s.recent.slice(0, 3).map((fc) => (
                  <li key={fc.id} className="flex items-start gap-2">
                    <span className={`mt-[6px] size-1.5 shrink-0 rounded-full ${dot(fc.verdict)}`} />
                    <span className="line-clamp-2 text-[12.5px] leading-snug">{fc.title}</span>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3 text-[11px] text-muted">Click to keep this state open</div>
          </>
        )}
      </div>
    </div>
  )
}

const LOC = Object.fromEntries(india.locations.map((l) => [l.id, l]))

export default function IndiaMap() {
  const { data, error, loading, reload } = useAsync(() => api.indiaMap(), [])
  const [mode, setMode] = useState<Mode>('crime')
  const [pinned, setPinned] = useState<string | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const liftEl = useRef<SVGPathElement>(null)
  const card = useRef<CardHandle | null>(null)
  const hideTimer = useRef<number | undefined>(undefined)
  const frame = useRef(0)
  const pop = useRef<Animation | null>(null)
  const dataRef = useRef<IndiaMapData | null>(null)
  const fillsRef = useRef<Record<string, string>>({})
  useEffect(() => () => { window.clearTimeout(hideTimer.current); cancelAnimationFrame(frame.current) }, [])

  const byCode = useMemo(() => Object.fromEntries((data?.states ?? []).map((s) => [s.code, s])) as Record<string, MapState>, [data])
  // Opening selection: among the five highest crime rates, the state named in most fact-checks.
  const initial = useMemo(() => [...(data?.states ?? [])].sort((a, b) => a.rate_rank - b.rate_rank).slice(0, 5)
    .sort((a, b) => b.mentions - a.mentions)[0]?.code, [data])
  const activeCode = pinned ?? initial
  const active = activeCode ? byCode[activeCode] : undefined
  const activeRegions = regionsOf(activeCode)

  const { fills, labels } = useMemo(() => {
    const fills: Record<string, string> = {}, labels: Record<string, string> = {}
    if (data) for (const l of india.locations) {
      const s = byCode[data.map_regions[l.id]]
      if (!s) continue
      fills[l.id] = mode === 'crime' ? fillFor(s.crime_rate) : claimFill(s.mentions)
      labels[l.id] = `${s.name}: ${rate1.format(s.crime_rate)} crimes per lakh, ${s.mentions} fact-checked claims`
    }
    return { fills, labels }
  }, [data, byCode, mode])
  useEffect(() => { dataRef.current = data ?? null; fillsRef.current = fills; if (liftEl.current) delete liftEl.current.dataset.id }, [data, fills])

  /* Hover is handled outside React. One spare <path> is re-pointed at the state under the pointer and
     raised (scale + shadow) with the Web Animations API, so it responds on the same frame and the 36
     base shapes are never touched. A short grace period on leave stops flashing between neighbours. */
  const lift = useCallback((regionId: string | null) => {
    const o = liftEl.current; if (!o) return
    window.clearTimeout(hideTimer.current)
    if (!regionId) { hideTimer.current = window.setTimeout(() => { o.style.opacity = '0'; delete o.dataset.id; card.current?.hide() }, 70); return }
    if (o.dataset.id !== regionId) {
      o.dataset.id = regionId
      o.setAttribute('d', LOC[regionId].path)
      o.setAttribute('fill', fillsRef.current[regionId] ?? '#ecece8')
      pop.current?.cancel() // one animation at a time; forwards-filled ones would otherwise pile up
      pop.current = o.animate([{ transform: 'scale(1)' }, { transform: 'scale(1.035)' }], { duration: 220, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'forwards' })
    }
    o.style.opacity = '1'
  }, [])
  const onEnter = useCallback((regionId: string) => {
    const d = dataRef.current; if (!d) return
    lift(regionId); card.current?.show(d.map_regions[regionId])
  }, [lift])
  const onLeave = useCallback(() => lift(null), [lift])
  const onPick = useCallback((regionId: string) => { const d = dataRef.current; if (d) setPinned(d.map_regions[regionId]) }, [])
  // From the table and the small-territory buttons: raise the state on the map, without the card.
  const onRowHover = useCallback((code: string | null) => lift(code ? regionsOf(code)[0] : null), [lift])
  const onRowPick = useCallback((code: string) => { setPinned(code); window.scrollTo({ top: 0, behavior: 'smooth' }) }, [])
  const onMove = (e: React.PointerEvent) => {
    const { clientX, clientY } = e
    cancelAnimationFrame(frame.current)
    frame.current = requestAnimationFrame(() => {
      const r = box.current?.getBoundingClientRect(); const c = card.current?.el()
      if (!r || !c) return
      const px = clientX - r.left, py = clientY - r.top, w = c.offsetWidth, h = c.offsetHeight
      const x = px + 20 + w > r.width ? px - 20 - w : px + 20 // flip to the left of the pointer near the edge
      const y = Math.min(Math.max(py - 24, 0), Math.max(0, r.height - h))
      c.style.transform = `translate3d(${Math.max(0, x)}px, ${y}px, 0)`
    })
  }

  const finding = useMemo(() => {
    if (!data) return ''
    const nat = data.crime_source.national_rate
    const top = [...data.states].sort((a, b) => a.rate_rank - b.rate_rank).slice(0, 2)
    const named = [...data.states].sort((a, b) => b.mentions - a.mentions).slice(0, 3).map((s) => s.name)
    return `${top[0].name} and ${top[1].name} register more than ${Math.floor(top[1].crime_rate / nat)} times the national rate of ${rate1.format(nat)}. The states named most often in fact-checked claims are ${named[0]}, ${named[1]} and ${named[2]}.`
  }, [data])

  const bins = mode === 'crime' ? BINS : CLAIM_BINS

  return (
    <div className="mx-auto max-w-[1160px] px-5 pt-8 md:px-8">
      <h1 className="font-serif text-[26px] font-semibold tracking-[-0.015em]">India map</h1>
      <p className="mt-1 max-w-[86ch] text-[14px] text-muted">Registered crime rate by state in 2023, and the viral claims fact-checkers investigated about each place. {finding}</p>

      {error && <div className="mt-6"><ErrorNote message={`Couldn't load the map data. ${error}`} onRetry={reload} /></div>}
      {loading && <Spinner label="Loading the map" />}

      {data && (
        <>
          <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1.3fr_1fr]">
            <section aria-label="Map of India" className="rounded-card border border-border bg-surface">
              <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2 px-5 pt-4">
                <div className="w-[250px]"><Tabs label="What the map shades" value={mode} onChange={setMode} options={[{ value: 'crime', label: 'Crime rate' }, { value: 'claims', label: 'Claims fact-checked' }]} /></div>
                <span className="pb-2 text-[12px] text-muted">{mode === 'crime' ? 'Registered crimes per lakh people, 2023' : 'Fact-checks naming the state'}</span>
              </div>

              <div ref={box} className="relative px-3 pt-2 md:px-6" onPointerMove={onMove}>
                <svg viewBox={india.viewBox} role="img" aria-label={mode === 'crime' ? 'India by state. Darker red means a higher registered crime rate.' : 'India by state. Darker blue means more fact-checked claims name the state.'} className="mx-auto block h-auto w-full max-w-[600px] overflow-visible">
                  <Shapes fills={fills} labels={labels} onEnter={onEnter} onLeave={onLeave} onPick={onPick} />
                  <g pointerEvents="none">
                    {india.locations.filter((l) => activeRegions.includes(l.id)).map((l) => (
                      <path key={l.id} d={l.path} fill="none" stroke="#111111" strokeWidth={2} strokeLinejoin="round" />
                    ))}
                  </g>
                  <path ref={liftEl} className="map-lift" strokeLinejoin="round" />
                </svg>
                <HoverCard handle={card} byCode={byCode} count={data.states.length} />
              </div>

              {/* small territories */}
              <div className="flex flex-wrap items-center gap-1.5 px-5 pt-3 text-[12px]">
                <span className="mr-1 text-muted">Too small to point at:</span>
                {SMALL.map((c) => byCode[c] && (
                  <button key={c} type="button" onPointerEnter={() => onRowHover(c)} onPointerLeave={() => onRowHover(null)} onClick={() => setPinned(c)}
                    className={`flex h-[26px] items-center gap-1.5 rounded-ctl border px-2 transition-colors duration-150 ${activeCode === c ? 'border-ink bg-raised' : 'border-border hover:border-muted'}`}>
                    <span className="size-2.5 rounded-[2px]" style={{ background: mode === 'crime' ? fillFor(byCode[c].crime_rate) : claimFill(byCode[c].mentions) }} />
                    {byCode[c].name.replace('Andaman and Nicobar Islands', 'Andaman & Nicobar').replace('Dadra and Nagar Haveli and Daman and Diu', 'DNH & Daman-Diu')}
                  </button>
                ))}
              </div>

              {/* legend: one stepped bar */}
              <div className="mt-4 border-t border-rule px-5 py-4">
                <div className="flex">
                  {bins.map((b) => (
                    <div key={b.label} className="flex-1">
                      <div className="h-2.5" style={{ background: b.fill, transition: 'background-color .3s' }} />
                      <div className="tnum mt-1.5 text-[11px] text-muted">{b.short}</div>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <StatePanel s={active} ladakh={activeCode === 'jk' ? byCode.la : undefined} national={data.crime_source.national_rate} count={data.states.length} />
          </div>

          <p className="mt-6 max-w-[100ch] rounded-card border border-[#f0dc9a] bg-warn-bg px-4 py-3 text-[13px] leading-relaxed text-warn-ink">
            A high rate is not a danger ranking. NCRB counts crimes that police registered, so states where people report more and police record more show higher numbers; NCRB itself warns against comparing states on these figures alone. Claims are fact-checks, not crimes: {nf.format(data.fact_checks_located)} of {nf.format(data.fact_checks_total)} fact-checks in the dataset name a state or one of its larger cities.
          </p>

          <h2 className={`mt-10 ${H2}`}>All states and union territories</h2>
          <p className="mt-1 text-[13px] text-muted">Sorted by {mode === 'crime' ? 'crime rate' : 'claims fact-checked'}, following the map. Select a row to open that state.</p>
          <StateTable data={data} mode={mode} activeCode={activeCode} onHover={onRowHover} onPick={onRowPick} />
          <p className="mt-3 max-w-[100ch] text-[12px] leading-relaxed text-muted">
            Crime figures: <a className="underline" href={data.crime_source.url} target="_blank" rel="noreferrer">{data.crime_source.name}</a>, IPC and SLL crimes together, as tabulated <a className="underline" href={data.crime_source.table_url} target="_blank" rel="noreferrer">here</a>. A claim that names two states is counted in both, so the claims column does not add up to its India row. Places are matched by name, so some are missed and shared names (Punjab, Hyderabad) can be misassigned. The map outline draws Ladakh inside Jammu and Kashmir, and Daman and Diu apart from Dadra and Nagar Haveli; their figures are listed separately above. Map shapes: @svg-maps/india, CC BY 4.0.
          </p>
        </>
      )}
    </div>
  )
}

function StatePanel({ s, ladakh, national, count }: { s?: MapState; ladakh?: MapState; national: number; count: number }) {
  if (!s) return null
  const ratio = s.crime_rate / national
  return (
    <section aria-live="polite" aria-label={`Details for ${s.name}`} className="rounded-card border border-border bg-surface p-5 lg:sticky lg:top-[68px]">
      <div>
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-serif text-[24px] leading-tight font-semibold tracking-[-0.01em]">{s.name}</h2>
          <span className="shrink-0 text-[12px] text-muted">Click a state to change</span>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-x-6 border-b border-rule pb-4">
          <div>
            <dt className="text-[12px] text-muted">Crimes per lakh, 2023</dt>
            <dd className="tnum mt-1 flex items-center gap-2 text-[30px] leading-none font-semibold">
              <span className="size-3 rounded-[2px]" style={{ background: fillFor(s.crime_rate) }} aria-hidden />{rate1.format(s.crime_rate)}
            </dd>
            <dd className="tnum mt-1.5 text-[12px] text-muted">Rank {s.rate_rank} of {count} · {ratio >= 1 ? `${ratio.toFixed(1)}× the India rate` : `${Math.round(ratio * 100)}% of the India rate`}</dd>
          </div>
          <div>
            <dt className="text-[12px] text-muted">Claims fact-checked</dt>
            <dd className="tnum mt-1 flex items-center gap-2 text-[30px] leading-none font-semibold">
              <span className="size-3 rounded-[2px]" style={{ background: claimFill(s.mentions) }} aria-hidden />{nf.format(s.mentions)}
            </dd>
            <dd className="tnum mt-1.5 text-[12px] text-muted">{s.mentions ? `${nf.format(s.false_mentions)} rated false` : 'none in the dataset'} · {nf.format(s.total_crimes)} crimes registered</dd>
          </div>
        </dl>
        {ladakh && <p className="tnum mt-3 text-[12px] text-muted">This outline also covers Ladakh: {rate1.format(ladakh.crime_rate)} per lakh, {nf.format(ladakh.mentions)} claims fact-checked.</p>}

        <h3 className="mt-4 text-[13px] font-semibold">Recent claims that went viral here</h3>
        {s.recent.length ? (
          <ul className="mt-1 divide-y divide-rule">
            {s.recent.map((fc) => (
              <li key={fc.id} className="py-2.5 last:pb-0">
                <a href={fc.original_url} target="_blank" rel="noreferrer" className="line-clamp-2 font-serif text-[15px] leading-snug font-semibold hover:underline">{fc.title}</a>
                <div className="mt-1 flex items-center gap-2 text-[12px] text-muted">
                  <Pill tone={verdictTone(fc.verdict)}>{verdictLabel(fc.verdict)}</Pill>
                  <span className="truncate">{fc.source_name} · {fmtDate(fc.publication_date)}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : <p className="mt-2 rounded-card border border-dashed border-control px-4 py-4 text-[13px] text-muted">No fact-check in the dataset names {s.name}.</p>}
        {s.mentions > s.recent.length && (
          <Link to={`/explorer?q=${encodeURIComponent(s.name)}`} className="mt-3 inline-block text-[13px] font-medium text-ink underline underline-offset-2">Search fact-checks for {s.name}</Link>
        )}
      </div>
    </section>
  )
}

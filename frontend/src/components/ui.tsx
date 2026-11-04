import type { ReactNode } from 'react'
import { AlertTriangle, Loader2 } from 'lucide-react'
import type { Tone } from '../utils/format'

const TONE: Record<Tone, string> = {
  neg: 'bg-neg-bg text-neg-ink',
  warn: 'bg-warn-bg text-warn-ink',
  pos: 'bg-pos-bg text-pos-ink',
  neu: 'bg-neu-bg text-neu-ink',
}

export function Pill({ tone = 'neu', children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={`inline-flex h-[22px] shrink-0 items-center rounded-full px-2.5 text-[12px] font-medium whitespace-nowrap ${TONE[tone]}`}>
      {children}
    </span>
  )
}

export function Panel({ title, aside, children, className = '', id }: {
  title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string; id?: string
}) {
  return (
    <section id={id} className={`rounded-[6px] border border-border bg-surface ${className}`}>
      {title && (
        <header className="flex items-baseline justify-between gap-4 px-5 pt-4 pb-3">
          <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
          {aside && <div className="text-[12px] text-muted">{aside}</div>}
        </header>
      )}
      <div className={title ? 'px-5 pb-5' : 'p-5'}>{children}</div>
    </section>
  )
}

export function Tabs<T extends string>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string
}) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-5 border-b border-border">
      {options.map((o) => (
        <button
          key={o.value} type="button" role="tab" aria-selected={o.value === value}
          data-active={o.value === value} onClick={() => onChange(o.value)}
          className={`sel-line -mb-px pb-2 text-[13px] transition-colors ${o.value === value ? 'text-ink' : 'text-muted hover:text-ink'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Spinner({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-6 text-[13px] text-muted">
      <Loader2 className="size-4 animate-spin" aria-hidden /> {label}
    </div>
  )
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-[6px] bg-neg-bg px-4 py-3 text-[13px] text-neg-ink">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="flex-1">{message}</div>
      {onRetry && <button onClick={onRetry} className="underline underline-offset-2 hover:text-ink">Retry</button>}
    </div>
  )
}

/** A horizontal bar used inside lists: value 0..1, one hue. */
export function Bar({ value, tone = 'accent', label }: { value: number; tone?: 'accent' | 'neg' | 'warn' | 'pos' | 'ink'; label?: string }) {
  const color = { accent: 'bg-accent', neg: 'bg-negative', warn: 'bg-warning', pos: 'bg-positive', ink: 'bg-ink/70' }[tone]
  return (
    <div className="h-1.5 w-full rounded-full bg-raised" role="img" aria-label={label}>
      <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  )
}

export function KV({ k, v }: { k: ReactNode; v: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-[13px]">
      <dt className="text-muted">{k}</dt>
      <dd className="tnum text-right text-ink">{v}</dd>
    </div>
  )
}

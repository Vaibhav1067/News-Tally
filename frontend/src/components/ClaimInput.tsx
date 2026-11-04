import { useState, type FormEvent } from 'react'
import { ArrowRight, Link2 } from 'lucide-react'
import { Tabs } from './ui'
import type { AnalyzeInput } from '../services/api'

type Mode = 'text' | 'url'

export const EXAMPLES = [
  { label: 'Deepfake video', text: 'Viral video shows Defence Minister Rajnath Singh criticising the Indian Army amid the India-China standoff in Arunachal Pradesh' },
  { label: 'Hindi forward', text: 'दिल्ली पुलिस ने प्रदर्शनकारी महिलाओं की पिटाई की, देखिए यह वीडियो और सबको भेजिए' },
  { label: 'Currency rumour', text: 'RBI has asked all banks to stop giving Rs 500 notes from ATMs from next month. Forward to everyone!' },
  { label: 'Unchecked claim', text: 'Vegetable prices in Bengaluru have doubled since last year according to local traders' },
]

export function ClaimInput({ onSubmit, busy, initial, compact = false }: {
  onSubmit: (input: AnalyzeInput) => void; busy?: boolean; initial?: AnalyzeInput; compact?: boolean
}) {
  const [mode, setMode] = useState<Mode>(initial?.url && !initial?.text ? 'url' : 'text')
  const [text, setText] = useState(initial?.text ?? '')
  const [url, setUrl] = useState(initial?.url ?? '')
  const [language, setLanguage] = useState(initial?.language ?? '')
  const [save, setSave] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function submit(e: FormEvent) {
    e.preventDefault()
    const t = text.trim(), u = url.trim()
    if (mode === 'text' && t.length < 2) return setError('Paste a claim, post or forward to analyse.')
    if (mode === 'url') {
      try { const p = new URL(u); if (!/^https?:$/.test(p.protocol)) throw new Error() } catch { return setError('Enter a full web address starting with https://') }
    }
    setError(null)
    onSubmit({ text: mode === 'text' ? t : undefined, url: mode === 'url' ? u : undefined, language: language || undefined, save_to_history: save })
  }

  return (
    <form data-ui onSubmit={submit} className="rounded-[6px] border border-border bg-surface" aria-label="Analyze a claim">
      <div className="px-5 pt-4">
        <Tabs label="Input type" value={mode} onChange={(m) => { setMode(m); setError(null) }}
          options={[{ value: 'text', label: 'Paste text' }, { value: 'url', label: 'Article URL' }]} />
      </div>
      <div className="px-5 pt-4">
        {mode === 'text' ? (
          <>
            <label htmlFor="claim" className="sr-only">Claim text</label>
            <textarea id="claim" value={text} onChange={(e) => setText(e.target.value)} maxLength={10000}
              rows={compact ? 3 : 5} placeholder="Paste a claim, a WhatsApp forward or a post — English, Hindi, Kannada or mixed"
              className="w-full resize-y bg-transparent text-[16px] leading-relaxed text-ink outline-none placeholder:text-muted" />
            <div className="tnum flex justify-end text-[13px] text-muted">{text.length.toLocaleString('en-IN')} / 10,000</div>
          </>
        ) : (
          <div className="flex items-center gap-3 pb-3">
            <Link2 className="size-4 text-muted" aria-hidden />
            <label htmlFor="url" className="sr-only">Article URL</label>
            <input id="url" type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://"
              className="h-10 w-full bg-transparent text-[16px] text-ink outline-none placeholder:text-muted" />
          </div>
        )}
      </div>
      {error && <p role="alert" className="px-5 pb-2 text-[13px] text-neg-ink">{error}</p>}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 border-t border-border px-5 py-3">
        <label className="flex items-center gap-2 text-[13px] text-muted">
          Language
          <select value={language} onChange={(e) => setLanguage(e.target.value)}
            className="h-[30px] rounded-full border border-control bg-ground px-3 text-[13px] text-ink">
            <option value="">Detect automatically</option>
            <option value="en">English</option>
            <option value="hi">Hindi</option>
            <option value="kn">Kannada</option>
          </select>
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-[13px] text-muted" title="Off by default. Saved text is deleted after the retention period.">
          <input type="checkbox" checked={save} onChange={(e) => setSave(e.target.checked)} className="size-4 accent-[#4a8ad6]" />
          Save to history
        </label>
        <button type="submit" disabled={busy}
          className="ml-auto inline-flex h-[38px] items-center gap-2 rounded-full bg-[#2f6db5] px-5 text-[14px] font-semibold text-white transition hover:bg-[#3b7cc6] active:scale-[0.98] disabled:opacity-60">
          {busy ? 'Analysing…' : 'Analyze claim'} <ArrowRight className="size-4" aria-hidden />
        </button>
      </div>
    </form>
  )
}

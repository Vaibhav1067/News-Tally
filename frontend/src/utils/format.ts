import type { RiskLevel } from '../types/api'

export const LANGUAGE_NAMES: Record<string, string> = {
  en: 'English', hi: 'Hindi', kn: 'Kannada', mixed: 'Mixed', 'hi-Latn': 'Hinglish', ta: 'Tamil', te: 'Telugu',
  bn: 'Bengali', mr: 'Marathi', ml: 'Malayalam', gu: 'Gujarati', pa: 'Punjabi', ur: 'Urdu', unknown: 'Unknown',
}

export const langName = (c?: string | null) => (c ? LANGUAGE_NAMES[c] ?? c : '—')

export const VERDICT_LABEL: Record<string, string> = {
  FALSE: 'False', MISLEADING: 'Misleading', OUTDATED: 'Outdated', TRUE: 'True', UNVERIFIED: 'Unverified',
  INSUFFICIENT_EVIDENCE: 'Insufficient evidence', UNPARSED: 'Not parsed',
}
export const verdictLabel = (v?: string | null) => VERDICT_LABEL[v ?? 'UNPARSED'] ?? v ?? 'Not parsed'

export type Tone = 'neg' | 'warn' | 'pos' | 'neu'

export const verdictTone = (v?: string | null): Tone =>
  v === 'FALSE' ? 'neg' : v === 'MISLEADING' || v === 'OUTDATED' ? 'warn' : v === 'TRUE' ? 'pos' : 'neu'

export const riskTone = (l: RiskLevel): Tone =>
  l === 'HIGH MISINFORMATION RISK' ? 'neg' : l === 'POTENTIALLY MISLEADING' ? 'warn'
    : l === 'EVIDENCE SUPPORTS CLAIM' ? 'pos' : 'neu'

export const RISK_TITLE: Record<RiskLevel, string> = {
  'HIGH MISINFORMATION RISK': 'High misinformation risk',
  'POTENTIALLY MISLEADING': 'Potentially misleading',
  'EVIDENCE SUPPORTS CLAIM': 'Evidence supports claim',
  UNVERIFIED: 'Unverified',
  'INSUFFICIENT EVIDENCE': 'Insufficient evidence',
}

export const nf = new Intl.NumberFormat('en-IN')
export const pct = (x: number, d = 0) => `${(x * 100).toFixed(d)}%`

export function fmtDate(iso?: string | null) {
  if (!iso) return '—'
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function ageText(days: number | null | undefined) {
  if (days == null) return 'date unknown'
  if (days < 1) return 'today'
  if (days === 1) return '1 day ago'
  if (days < 60) return `${days} days ago`
  if (days < 730) return `${Math.round(days / 30.4)} months ago`
  return `${(days / 365.25).toFixed(1)} years ago`
}

export const MODEL_NAMES: Record<string, string> = {
  dummy_most_frequent: 'Baseline: most frequent class', dummy_stratified: 'Baseline: random (stratified)',
  multinomial_nb: 'Multinomial Naive Bayes', complement_nb: 'Complement Naive Bayes',
  logistic_regression: 'Logistic Regression', linear_svm: 'Linear SVM (calibrated)',
}

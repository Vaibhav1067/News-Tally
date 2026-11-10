// Mirrors backend/app/schemas/__init__.py — the API contract.

export type RiskLevel =
  | 'HIGH MISINFORMATION RISK'
  | 'POTENTIALLY MISLEADING'
  | 'EVIDENCE SUPPORTS CLAIM'
  | 'UNVERIFIED'
  | 'INSUFFICIENT EVIDENCE'

export type Verdict = 'FALSE' | 'MISLEADING' | 'TRUE' | 'UNVERIFIED' | 'OUTDATED' | 'INSUFFICIENT_EVIDENCE'

export interface LanguageInfo {
  code: string
  name: string
  confidence: number
  is_mixed: boolean
  method: string
  supported_by_model: boolean
  user_hint?: string | null
}

export interface ExtractedContent {
  text: string
  source: 'text' | 'url' | 'text+url'
  url?: string | null
  title?: string | null
  char_count: number
  truncated: boolean
  urls_in_text: string[]
  extraction_error?: string | null
}

export interface Prediction {
  available: boolean
  label?: string | null
  probabilities: Record<string, number>
  confidence?: number | null
  model_name?: string | null
  in_domain: boolean
  note: string
}

export interface FactCheckMatch {
  id: string
  claim_text: string
  title: string | null
  verdict: Verdict | null
  explanation: string | null
  source_name: string
  original_url: string
  language: string | null
  publication_date: string | null
  similarity: number
  match_strength: 'strong' | 'related' | 'weak'
  age_days: number | null
}

export interface SourceInfo {
  domain: string | null
  name?: string | null
  source_type?: string | null
  status: 'no_url' | 'insufficient_history' | 'known_source' | 'fact_checker'
  mentions_in_dataset: number
  verdict_breakdown: Record<string, number>
  example_fact_checks: { id: string; title: string; verdict: string | null; url: string; publication_date: string | null }[]
  coverage_note: string
  limitations: string[]
}

export interface FeatureContribution { feature: string; kind: 'word' | 'char'; contribution: number }

export interface Explanation {
  available: boolean
  method?: string | null
  target_class?: string | null
  top_features: FeatureContribution[]
  token_highlights: { token: string; score: number }[]
  note: string
  reason?: string | null
}

export interface ScoreComponent { name: string; value: number | null; weight: number; available: boolean; detail: string }

export interface RiskAssessment {
  level: RiskLevel
  risk_score: number
  evidence_strength: number
  evidence_strength_label: 'High' | 'Medium' | 'Low'
  summary: string
  reasons: string[]
  missing_evidence: string[]
  components: ScoreComponent[]
  formula: string
}

export interface AnalyzeResponse {
  analysis_id: string
  detected_language: LanguageInfo
  extracted_content: ExtractedContent
  prediction: Prediction
  confidence: number | null
  risk_assessment: RiskAssessment
  matching_fact_checks: FactCheckMatch[]
  source_information: SourceInfo
  explanation: Explanation
  retrieval_backend: string
  processing_time_ms: number
  stored: boolean
  disclaimer: string
}

export interface FactCheck {
  id: string
  claim_text: string
  claim_source: string | null
  title: string | null
  verdict: Verdict | null
  verdict_raw: string | null
  verdict_rule: string | null
  explanation: string | null
  source_name: string
  original_url: string
  category: string | null
  category_source: string | null
  language: string | null
  publication_date: string | null
}

export interface FactCheckPage { items: FactCheck[]; total: number; page: number; page_size: number }

export interface Facets { languages: string[]; verdicts: string[]; sources: string[]; categories: string[] }

export interface Statistics {
  total_fact_checks: number
  verdict_distribution: Record<string, number>
  language_distribution: Record<string, number>
  source_distribution: Record<string, number>
  category_distribution: Record<string, number>
  timeline: { month: string; count: number }[]
  language_by_verdict: Record<string, Record<string, number>>
  date_range: [string | null, string | null]
  analyses_run: number
  data_quality: Record<string, unknown> & {
    raw_rows?: number; final_rows?: number; duplicate_pct?: number; near_duplicate_rows?: number
    invalid_rows?: number; missing_pct_processed?: Record<string, number>; built_at?: string
    claim_source_distribution?: Record<string, number>; category_source_distribution?: Record<string, number>
  }
  note: string
}

export interface ClassMetrics { precision: number; recall: number; f1: number; support: number }

export interface ModelsInfo {
  components: Record<string, { available: boolean; [k: string]: unknown }>
  classifier: {
    deployed_model: string; best_validation_model: string; classes: string[]; task: string
    n_train: number; n_val: number; n_test: number; split: string; features: string; trained_at: string
    label_distribution_train: Record<string, number>
    deployed_breakdown_test: Record<string, Record<string, { n: number; f1_macro: number; accuracy: number }>>
  }
  comparison: Record<string, { validation_macro_f1: number; test_macro_f1: number; test_accuracy: number; test_weighted_f1: number; test_ece: number | null }>
  deployed_test_metrics: {
    accuracy: number; f1_macro: number; f1_weighted: number; per_class: Record<string, ClassMetrics>
    confusion_matrix: { labels: string[]; matrix: number[][] }; calibration?: { ece: number }
  } | null
  retrieval_evaluation: Record<string, any> | null
  transformer_experiment: Record<string, any> | null
}

export interface HistoryItem {
  id: string; text_preview: string | null; submitted_url: string | null; detected_language: string | null
  predicted_class: string | null; risk_level: RiskLevel | null; risk_score: number | null; created_at: string
}

export interface MapFactCheck { id: string; title: string; verdict: string | null; source_name: string; language: string | null; original_url: string; publication_date: string | null }
export interface MapState { code: string; name: string; total_crimes: number; crime_rate: number; rate_rank: number; mentions: number; false_mentions: number; recent: MapFactCheck[] }
export interface IndiaMapData {
  crime_source: { name: string; measure: string; url: string; table_url: string; national_rate: number; national_total: number }
  map_regions: Record<string, string>; states: MapState[]; fact_checks_total: number; fact_checks_located: number
}

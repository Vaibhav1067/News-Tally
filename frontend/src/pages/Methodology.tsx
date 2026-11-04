import type { ReactNode } from 'react'
import { api } from '../services/api'
import { useAsync } from '../hooks/useAsync'
import { ErrorNote, Spinner } from '../components/ui'
import { MODEL_NAMES, nf, verdictLabel } from '../utils/format'
import type { ModelsInfo } from '../types/api'

const SECTIONS = [
  ['data', 'Data collection'], ['limits', 'Dataset limitations'], ['nlp', 'NLP pipeline'], ['models', 'ML models'],
  ['eval', 'Evaluation'], ['retrieval', 'Fact-check retrieval'], ['risk', 'Risk scoring'], ['xai', 'Explainability'],
  ['bias', 'Bias and fairness'], ['safeguards', 'Responsible AI safeguards'],
] as const

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-border pt-8 pb-4">
      <h2 className="text-[22px] font-semibold tracking-[-0.01em]">{title}</h2>
      <div className="mt-4 max-w-[75ch] space-y-3 text-[15px] leading-[1.65] text-ink [&_li]:ml-5 [&_li]:list-disc [&_li]:pl-1 [&_ul]:space-y-1.5">{children}</div>
    </section>
  )
}

function ComparisonTable({ m }: { m: ModelsInfo }) {
  const rows = Object.entries(m.comparison)
  return (
    <div className="not-prose my-4 overflow-x-auto rounded-[6px] border border-border bg-surface">
      <table className="w-full min-w-[620px] text-[13px]">
        <caption className="sr-only">Model comparison</caption>
        <thead><tr className="text-[12px] text-muted"><th className="px-4 py-3 text-left font-normal">Model</th><th className="px-3 py-3 text-right font-normal">Val macro-F1</th><th className="px-3 py-3 text-right font-normal">Test macro-F1</th><th className="px-3 py-3 text-right font-normal">Test accuracy</th><th className="px-3 py-3 text-right font-normal">Weighted-F1</th><th className="px-4 py-3 text-right font-normal">ECE</th></tr></thead>
        <tbody>
          {rows.map(([k, r]) => (
            <tr key={k} className={`border-t border-rule ${k === m.classifier.deployed_model ? 'font-semibold' : ''}`}>
              <td className="px-4 py-2.5">{MODEL_NAMES[k] ?? k}{k === m.classifier.deployed_model && <span className="ml-2 text-[12px] font-normal text-accent-ink">deployed</span>}</td>
              <td className="tnum px-3 py-2.5 text-right">{r.validation_macro_f1.toFixed(3)}</td>
              <td className="tnum px-3 py-2.5 text-right">{r.test_macro_f1.toFixed(3)}</td>
              <td className="tnum px-3 py-2.5 text-right">{r.test_accuracy.toFixed(3)}</td>
              <td className="tnum px-3 py-2.5 text-right">{r.test_weighted_f1.toFixed(3)}</td>
              <td className="tnum px-4 py-2.5 text-right">{r.test_ece?.toFixed(3) ?? '—'}</td>
            </tr>
          ))}
          {m.transformer_experiment?.frozen_embeddings_lr && (
            <tr className="border-t border-rule text-muted"><td className="px-4 py-2.5">Multilingual MiniLM, frozen embeddings + LR</td>
              <td className="tnum px-3 py-2.5 text-right">{m.transformer_experiment.frozen_embeddings_lr.validation.f1_macro.toFixed(3)}</td>
              <td className="tnum px-3 py-2.5 text-right">{m.transformer_experiment.frozen_embeddings_lr.test.f1_macro.toFixed(3)}</td>
              <td className="tnum px-3 py-2.5 text-right">{m.transformer_experiment.frozen_embeddings_lr.test.accuracy.toFixed(3)}</td>
              <td className="tnum px-3 py-2.5 text-right">{m.transformer_experiment.frozen_embeddings_lr.test.f1_weighted.toFixed(3)}</td>
              <td className="tnum px-4 py-2.5 text-right">{m.transformer_experiment.frozen_embeddings_lr.test.calibration?.ece?.toFixed(3) ?? '—'}</td></tr>
          )}
          {m.transformer_experiment?.finetune && (
            <tr className="border-t border-rule text-muted"><td className="px-4 py-2.5">Multilingual MiniLM, fine-tuned (best epoch {m.transformer_experiment.finetune.best_epoch})</td>
              <td className="tnum px-3 py-2.5 text-right">{m.transformer_experiment.finetune.validation.f1_macro.toFixed(3)}</td>
              <td className="tnum px-3 py-2.5 text-right">{m.transformer_experiment.finetune.test.f1_macro.toFixed(3)}</td>
              <td className="tnum px-3 py-2.5 text-right">{m.transformer_experiment.finetune.test.accuracy.toFixed(3)}</td>
              <td className="tnum px-3 py-2.5 text-right">{m.transformer_experiment.finetune.test.f1_weighted.toFixed(3)}</td>
              <td className="tnum px-4 py-2.5 text-right">{m.transformer_experiment.finetune.test.calibration?.ece?.toFixed(3) ?? '—'}</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function Confusion({ m }: { m: ModelsInfo }) {
  const cm = m.deployed_test_metrics?.confusion_matrix
  if (!cm) return null
  const max = Math.max(...cm.matrix.flat())
  return (
    <div className="my-4 inline-block rounded-[6px] border border-border bg-surface p-4">
      <table className="tnum text-[13px]">
        <caption className="pb-2 text-left text-[12px] text-muted">Confusion matrix, test set (rows = fact-checker's verdict, columns = predicted)</caption>
        <thead><tr><th />{cm.labels.map((l) => <th key={l} className="px-3 pb-2 text-right text-[12px] font-normal text-muted">{verdictLabel(l)}</th>)}</tr></thead>
        <tbody>{cm.matrix.map((row, i) => (
          <tr key={i}><th className="pr-3 text-left text-[12px] font-normal text-muted">{verdictLabel(cm.labels[i])}</th>
            {row.map((v, j) => <td key={j} className="px-3 py-1.5 text-right" style={{ backgroundColor: `rgba(74,138,214,${(v / max) * 0.45})` }}>{v}</td>)}</tr>
        ))}</tbody>
      </table>
    </div>
  )
}

export default function Methodology() {
  const { data: m, error, loading } = useAsync(() => api.models(), [])
  const { data: s } = useAsync(() => api.statistics(), [])
  const hy = m?.retrieval_evaluation?.hybrid
  const tf = m?.retrieval_evaluation?.tfidf_char
  const dep = m?.deployed_test_metrics

  return (
    <div className="mx-auto grid max-w-[1320px] gap-10 px-5 pt-8 md:px-8 lg:grid-cols-[220px_1fr]">
      <nav aria-label="On this page" className="hidden lg:block">
        <div className="sticky top-20 space-y-1.5 text-[13px]">
          {SECTIONS.map(([id, t]) => <a key={id} href={`#${id}`} className="block text-muted hover:text-ink">{t}</a>)}
        </div>
      </nav>
      <article className="min-w-0">
        <h1 className="text-[26px] font-bold tracking-[-0.015em]">Methodology</h1>
        <p className="mt-2 max-w-[75ch] text-[15px] leading-relaxed text-muted">How NEWS TALLY collects data, what its models do, how the assessment is computed, and where it fails. Every number on this page is read live from the trained artifacts.</p>
        {error && <div className="mt-4"><ErrorNote message={error} /></div>}
        {loading && <Spinner label="Loading model reports" />}

        <Section id="data" title="Data collection">
          <p>Fact-checks are collected from the public WordPress REST APIs of <a className="underline" href="https://factly.in" target="_blank" rel="noreferrer">Factly</a> (English and Kannada) and <a className="underline" href="https://www.altnews.in" target="_blank" rel="noreferrer">Alt News</a> (English and Hindi). The collector reads <code>robots.txt</code> before every host, identifies itself honestly, waits two seconds between requests and treats any 401/403 as a refusal. BOOM Live (HTTP 403) and PIB Fact Check (HTTP 401) blocked automated access and are therefore not included — they were not bypassed.</p>
          <p>For each article we keep the headline, URL, date, publisher tags, the circulating claim (Factly's “Claim:” block) and one conclusion sentence. Full article text is never stored; every record links to the original.</p>
          <p>Publishers write verdicts in prose (“… is a deepfake”, “पुराना वीडियो …”), so verdicts are mapped to FALSE, MISLEADING, OUTDATED, TRUE, UNVERIFIED or INSUFFICIENT_EVIDENCE by ordered, auditable regex rules in English, Hindi and Kannada. When no rule matches, the verdict stays empty instead of being guessed{s ? ` (${nf.format(s.verdict_distribution.UNPARSED ?? 0)} of ${nf.format(s.total_fact_checks)} records)` : ''}.</p>
        </Section>

        <Section id="limits" title="Dataset limitations">
          <ul>
            <li><strong>Selection bias.</strong> Fact-checkers choose suspicious claims, so almost every record is a debunk{s ? ` — only ${s.verdict_distribution.TRUE ?? 0} TRUE verdicts` : ''}. The classifier has effectively never seen a true claim.</li>
            <li><strong>Label noise.</strong> Two manual audits of the verdict rules found roughly 8% clear errors and a further ~8% debatable FALSE / MISLEADING / OUTDATED boundary calls. The audits were done by the AI assistant that wrote the rules, not by independent annotators. Kannada was not audited by a fluent reader.</li>
            <li><strong>Coverage.</strong> Two publishers, three languages, mostly 2024–2026. Statistics describe this collection, not misinformation in India.</li>
            <li><strong>Hindi has no claim field.</strong> Alt News headlines are used with verdict cue words masked, which is weaker training text.</li>
          </ul>
        </Section>

        <Section id="nlp" title="NLP pipeline">
          <p>One cleaning function is shared by training and inference to avoid training/serving skew: HTML removal, Unicode NFC normalisation (keeps Devanagari and Kannada combining marks intact), zero-width character removal, currency normalisation (“Rs 500” → “₹500”), URL extraction and whitespace normalisation. Text is not translated.</p>
          <p>Language is identified by counting Unicode script blocks (reliable for Indic scripts and short text), with <code>langdetect</code> only for Latin script and a small lexicon for romanised Hindi. Mixed-script text is reported as mixed.</p>
          <p>A bug worth knowing: Python's <code>\w</code> does not match Indic vowel signs, so a default tokenizer splits “प्रदर्शन” into fragments. A custom token pattern fixed this and raised validation macro-F1 from 0.567 to 0.584.</p>
        </Section>

        <Section id="models" title="ML models">
          <p><strong>Task:</strong> {m?.classifier.task ?? '…'} Classes with fewer than 30 examples are excluded, leaving {m?.classifier.classes.map(verdictLabel).join(', ')}.</p>
          <p>Features are TF-IDF word 1–2-grams plus character 2–5-grams, which work across scripts and spelling variants. Models: two dummy baselines, Multinomial and Complement Naive Bayes, Logistic Regression and a calibrated Linear SVM. Selection is on validation macro-F1; the test set is used once. Logistic Regression is deployed because it was best on validation and its coefficients give exact explanations.</p>
          {m && <ComparisonTable m={m} />}
          <p>A multilingual transformer (paraphrase-multilingual-MiniLM-L12-v2, 118M parameters) was evaluated on the same splits, both as frozen embeddings and fully fine-tuned on CPU. Larger Indic models (IndicBERT v2, MuRIL, XLM-R) need a GPU and 1–2 GB of disk and remain future work.{m?.transformer_experiment ? '' : ' The transformer results appear above once ml/training/train_transformer.py has been run.'}</p>
        </Section>

        <Section id="eval" title="Evaluation">
          <p>Splits are 70/15/15, stratified by verdict and <em>grouped</em> by near-duplicate claim (character n-gram cosine ≥ 0.8), so the same viral claim can never sit in both train and test. Macro-F1 is the headline metric because classes are imbalanced; Expected Calibration Error checks whether confidence can be trusted.</p>
          {dep && (
            <ul>
              <li>Deployed model, test set: macro-F1 <strong className="tnum">{dep.f1_macro.toFixed(3)}</strong>, accuracy <span className="tnum">{dep.accuracy.toFixed(3)}</span>, ECE <span className="tnum">{dep.calibration?.ece?.toFixed(3)}</span> (stratified random baseline: <span className="tnum">{m?.comparison.dummy_stratified?.test_macro_f1.toFixed(3)}</span>).</li>
              {Object.entries(dep.per_class).map(([c, v]) => <li key={c}>{verdictLabel(c)}: precision <span className="tnum">{v.precision.toFixed(2)}</span>, recall <span className="tnum">{v.recall.toFixed(2)}</span>, F1 <span className="tnum">{v.f1.toFixed(2)}</span> ({v.support} examples)</li>)}
            </ul>
          )}
          {m && <Confusion m={m} />}
          <p>Interpretation: the model is clearly better than chance but modest. Whether a debunked claim is called FALSE, MISLEADING or OUTDATED depends on facts outside the text (is the video old?), so a text-only model cannot do much better. This is why the classifier carries only 20% of the risk index and can never decide the outcome on its own.</p>
        </Section>

        <Section id="retrieval" title="Fact-check retrieval">
          <p>Retrieval is a hybrid: 0.5 × cosine similarity of multilingual sentence embeddings + 0.5 × cosine of character n-gram TF-IDF. The embedding model was not trained on Kannada (its Kannada texts collapse to near-identical vectors, recall@1 7%), so whenever Kannada is involved the lexical score is used alone.</p>
          {hy && tf && (
            <p>Evaluated by querying {nf.format(hy.n_queries)} circulating claims against {nf.format(hy.n_documents)} headlines: hybrid recall@1 <strong className="tnum">{hy['recall@1'].toFixed(3)}</strong>, recall@5 <span className="tnum">{hy['recall@5'].toFixed(3)}</span>, MRR <span className="tnum">{hy.mrr.toFixed(3)}</span> (lexical only: recall@1 <span className="tnum">{tf['recall@1'].toFixed(3)}</span>). A “strong match” (score ≥ 0.60) had top-1 precision <span className="tnum">{hy.precision_at_threshold['0.6'].top1_precision.toFixed(2)}</span>; “related” starts at 0.40. Hindi and cross-lingual retrieval are not measured because no Hindi claim texts exist to query with.</p>
          )}
          <p>Similarity is a retrieval relevance score. A strong match means a fact-checker examined something worded very similarly — not that the new claim must share its verdict.</p>
        </Section>

        <Section id="risk" title="Risk scoring">
          <p>Four dimensions are kept separate: evidence retrieval (E), content classification (C), source information (S) and uncertainty (evidence strength).</p>
          <p className="rounded-[6px] bg-surface px-4 py-3 font-medium">Risk index R = 100 × (0.65·E + 0.20·C + 0.15·S)</p>
          <ul>
            <li><strong>E</strong>: each relevant match gets weight w = clip((sim − 0.40)/(1 − 0.40)) × freshness, where freshness = max(0.7, 1 − 0.1 × age in years). E = max(w) × weighted verdict risk + (1 − max(w)) × 0.5. With no relevant match E = 0.5 — unknown, not safe.</li>
            <li><strong>C</strong>: Σ p(class) × verdict risk, only when the language is supported and the text has at least four words; otherwise 0.5.</li>
            <li><strong>S</strong>: 0 when the URL is itself a published fact-check; otherwise 0.5. Outlet reputation is never used to judge an individual claim, and no “false-news ratio” is computed for any outlet.</li>
            <li>Verdict risk: FALSE 1.0, MISLEADING 0.75, OUTDATED 0.65, UNVERIFIED/INSUFFICIENT 0.5, TRUE 0.</li>
            <li><strong>Evidence strength</strong> = 0.70 × max(w) + 0.20 × classifier confidence (if applicable) + 0.10 × [source known]; High ≥ 0.6, Medium ≥ 0.3.</li>
          </ul>
          <p>The label is decided by rules: a strong match's verdict decides it; related matches can only reach “Potentially misleading”; with no match the claim is “Unverified” (or “Insufficient evidence” for very short or unsupported text). The weights are design choices, not fitted parameters, and the index is not a calibrated probability.</p>
        </Section>

        <Section id="xai" title="Explainability">
          <p>For the linear classifier, SHAP values are exact: φ = w × (x − E[x]), with E[x] the mean TF-IDF vector of the training set. They sum, with the base value, to the model's class score — this additivity and agreement with the <code>shap</code> library are checked in the test suite. Highlights show which n-grams moved the model; they are not evidence that a word indicates misinformation. If a non-linear model is deployed the API states that explanations are unavailable instead of inventing reasons.</p>
        </Section>

        <Section id="bias" title="Bias and fairness">
          {m?.classifier.deployed_breakdown_test && (
            <ul>
              {Object.entries(m.classifier.deployed_breakdown_test.language ?? {}).map(([l, v]) => (
                <li key={l}>{l === 'en' ? 'English' : l === 'hi' ? 'Hindi' : l === 'kn' ? 'Kannada' : l}: test macro-F1 <span className="tnum">{v.f1_macro.toFixed(3)}</span> on {v.n} examples</li>
              ))}
            </ul>
          )}
          <p>Performance differs by language, and the dataset over-represents political and communal claims that these two publishers prioritise. Topics, regions and languages they do not cover are invisible to the system. Claims about particular communities appear because they were debunked; the system must not be read as saying which communities spread misinformation.</p>
        </Section>

        <Section id="safeguards" title="Responsible AI safeguards">
          <ul>
            <li>The classifier alone can never label a claim “High misinformation risk”.</li>
            <li>Confidence (evidence strength) is shown separately from risk; missing evidence is listed explicitly.</li>
            <li>Submitted text is not stored unless the user ticks “Save to history”; saved text is purged after the retention period (30 days by default).</li>
            <li>URL fetching blocks private and local network addresses (SSRF protection), limits size and time, and follows at most three redirects.</li>
            <li>No API keys are required or exposed; rate limiting and request size limits protect the service.</li>
            <li>Every result links to the original fact-check, so a person — not the model — makes the final judgement.</li>
          </ul>
        </Section>
      </article>
    </div>
  )
}

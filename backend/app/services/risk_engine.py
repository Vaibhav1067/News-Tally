"""Trust & risk assessment engine.

Inputs are kept as SEPARATE dimensions and never collapsed blindly:

    A. content classification  (classifier probabilities; weak evidence)
    B. evidence retrieval      (similar published fact-checks; strongest evidence)
    C. source information      (is the submitted URL itself a fact-check?)
    D. uncertainty             (how much evidence we actually have)

Outcome label (decision rules, evaluated in order)
-------------------------------------------------
1. A STRONG match (cosine >= strong threshold) exists:
       its verdict decides: FALSE -> HIGH MISINFORMATION RISK;
       MISLEADING / OUTDATED -> POTENTIALLY MISLEADING; TRUE -> EVIDENCE SUPPORTS CLAIM;
       UNVERIFIED -> UNVERIFIED; INSUFFICIENT_EVIDENCE / unparsed -> INSUFFICIENT EVIDENCE.
2. Only RELATED matches: POTENTIALLY MISLEADING if most related-match weight
   carries FALSE/MISLEADING/OUTDATED verdicts, else UNVERIFIED.
3. No relevant fact-check: UNVERIFIED if we could analyse the text,
   INSUFFICIENT EVIDENCE if the text is too short or in an unsupported language.
   The classifier can NEVER on its own produce a "high risk" or "supports" label.

Risk score (0–100, a heuristic index — NOT a calibrated probability)
-------------------------------------------------------------------
    R = 100 * (0.65 * E + 0.20 * C + 0.15 * S)

    E = evidence signal. With relevant matches m (weight w_m, verdict v_m):
            w_m = clip((sim_m - t_related) / (1 - t_related), 0, 1) * freshness_m
            E   = max_m(w_m) * Σ w_m·risk(v_m) / Σ w_m  +  (1 - max_m(w_m)) * 0.5
        i.e. weak matches pull E only slightly away from the neutral 0.5.
        No relevant match -> E = 0.5 (unknown, not "safe").
    C = classifier signal = Σ_k p_k · risk(k) when the language is supported, else 0.5.
    S = source signal: 0.0 when the URL is itself a published fact-check (the content
        is a debunk/verification, not the claim); otherwise 0.5 (neutral). We do not
        derive a "false-news ratio" for outlets from how often they are mentioned.
    risk(v): FALSE 1.0, MISLEADING 0.75, OUTDATED 0.65, UNVERIFIED 0.5,
             INSUFFICIENT_EVIDENCE 0.5, TRUE 0.0
    freshness = max(0.7, 1 - 0.1 · age_years)

Evidence strength (0–1, shown separately from risk)
--------------------------------------------------
    ES = 0.70 · max_m(w_m) + 0.20 · classifier_confidence · in_domain + 0.10 · [source known]
    High >= 0.6, Medium >= 0.3, else Low.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

VERDICT_RISK = {"FALSE": 1.0, "MISLEADING": 0.75, "OUTDATED": 0.65, "UNVERIFIED": 0.5,
                "INSUFFICIENT_EVIDENCE": 0.5, "TRUE": 0.0}
RISKY = {"FALSE", "MISLEADING", "OUTDATED"}
W_E, W_C, W_S = 0.65, 0.20, 0.15

FORMULA = ("R = 100 × (0.65·E + 0.20·C + 0.15·S); E = evidence from matched fact-checks "
           "(neutral 0.5 when none), C = classifier expected risk (0.5 if unsupported language), "
           "S = source signal (0 if the URL is itself a fact-check, else 0.5). "
           "Heuristic index, not a probability.")


@dataclass
class MatchInput:
    verdict: Optional[str]
    similarity: float
    age_days: Optional[int]
    title: str = ""
    source_name: str = ""


@dataclass
class RiskInput:
    matches: list[MatchInput]
    strong_threshold: float
    related_threshold: float
    class_probabilities: dict[str, float] = field(default_factory=dict)
    classifier_in_domain: bool = False
    text_too_short: bool = False
    source_is_fact_checker: bool = False
    source_known: bool = False
    source_name: Optional[str] = None


@dataclass
class RiskOutput:
    level: str
    risk_score: float
    evidence_strength: float
    evidence_strength_label: str
    summary: str
    reasons: list[str]
    missing_evidence: list[str]
    components: list[dict]
    formula: str = FORMULA


def freshness(age_days: Optional[int]) -> float:
    if age_days is None:
        return 0.85
    return max(0.7, 1 - 0.1 * (age_days / 365.25))


def match_weight(m: MatchInput, related_t: float) -> float:
    base = (m.similarity - related_t) / (1 - related_t)
    return max(0.0, min(1.0, base)) * freshness(m.age_days)


def _level_for_verdict(v: Optional[str]) -> str:
    if v == "FALSE":
        return "HIGH MISINFORMATION RISK"
    if v in ("MISLEADING", "OUTDATED"):
        return "POTENTIALLY MISLEADING"
    if v == "TRUE":
        return "EVIDENCE SUPPORTS CLAIM"
    if v == "UNVERIFIED":
        return "UNVERIFIED"
    return "INSUFFICIENT EVIDENCE"


def assess(inp: RiskInput) -> RiskOutput:
    reasons: list[str] = []
    missing: list[str] = []
    relevant = [m for m in inp.matches if m.similarity >= inp.related_threshold]
    strong = [m for m in relevant if m.similarity >= inp.strong_threshold]

    # ---- E: evidence --------------------------------------------------------
    weights = [match_weight(m, inp.related_threshold) for m in relevant]
    if relevant and sum(weights) > 0:
        wmax = max(weights)
        avg = sum(w * VERDICT_RISK.get(m.verdict or "", 0.5) for w, m in zip(weights, relevant)) / sum(weights)
        E = wmax * avg + (1 - wmax) * 0.5
        e_detail = f"{len(relevant)} relevant fact-check(s); strongest match weight {wmax:.2f}"
    else:
        wmax, E = 0.0, 0.5
        e_detail = "No sufficiently similar fact-check found (neutral 0.5)"
        missing.append("No published fact-check in our dataset closely matches this claim.")

    # ---- C: classifier --------------------------------------------------------
    if inp.class_probabilities and inp.classifier_in_domain:
        C = sum(p * VERDICT_RISK.get(k, 0.5) for k, p in inp.class_probabilities.items())
        cls_conf = max(inp.class_probabilities.values())
        c_detail = (f"Expected verdict-risk {C:.2f} under classifier probabilities "
                    f"(top class {max(inp.class_probabilities, key=inp.class_probabilities.get)}, p={cls_conf:.2f})")
    else:
        C, cls_conf = 0.5, 0.0
        c_detail = "Classifier not applicable (unsupported language or too little text); neutral 0.5"
        missing.append("The text classifier could not be applied reliably to this input.")

    # ---- S: source -----------------------------------------------------------
    if inp.source_is_fact_checker:
        S, s_detail = 0.0, f"Submitted URL is a published fact-check by {inp.source_name}"
    else:
        S = 0.5
        s_detail = "Neutral: outlet reputation is not used to judge an individual claim"
        if not inp.source_known:
            missing.append("Insufficient source history for the submitted URL (or no URL given).")

    risk = 100 * (W_E * E + W_C * C + W_S * S)
    es = 0.70 * wmax + 0.20 * cls_conf * (1 if inp.classifier_in_domain else 0) + 0.10 * (1 if inp.source_known else 0)
    es = round(min(1.0, es), 3)
    es_label = "High" if es >= 0.6 else "Medium" if es >= 0.3 else "Low"

    # ---- outcome label --------------------------------------------------------
    if inp.source_is_fact_checker:
        level = "INSUFFICIENT EVIDENCE" if not strong else _level_for_verdict(strong[0].verdict)
        summary = (f"This link is a fact-check published by {inp.source_name}. Read its verdict directly; "
                   "the score reflects the claim it examines.")
        reasons.append(summary)
    elif strong:
        best = max(strong, key=lambda m: m.similarity)
        level = _level_for_verdict(best.verdict)
        verdict_txt = best.verdict or "an unparsed verdict"
        summary = (f"A closely matching claim was fact-checked by {best.source_name} and rated {verdict_txt}. "
                   "Check that it is the same claim before relying on it.")
        reasons.append(f"Strong match (similarity {best.similarity:.2f}) with: \"{best.title[:140]}\"")
        if best.verdict is None:
            missing.append("The matched fact-check's verdict could not be parsed automatically; open the original.")
    elif relevant:
        risky_w = sum(w for w, m in zip(weights, relevant) if m.verdict in RISKY)
        level = "POTENTIALLY MISLEADING" if risky_w > 0.5 * sum(weights) and sum(weights) > 0 else "UNVERIFIED"
        summary = ("Related fact-checks exist on a similar topic, but none is a close match. "
                   "Treat the claim as unconfirmed and compare with the references.")
        reasons.append(f"{len(relevant)} related fact-check(s) found; none above the strong-match threshold.")
    elif inp.text_too_short or not inp.classifier_in_domain:
        level = "INSUFFICIENT EVIDENCE"
        summary = "There is not enough text or language support to assess this content."
        reasons.append("Input too short or in a language the model was not trained on.")
    else:
        level = "UNVERIFIED"
        summary = ("No matching fact-check was found. This does not mean the claim is true or false — "
                   "it has simply not been verified in our dataset.")
        reasons.append("No relevant fact-check found in the dataset.")

    if inp.class_probabilities and inp.classifier_in_domain:
        top = max(inp.class_probabilities, key=inp.class_probabilities.get)
        reasons.append(f"Language-pattern model: among previously fact-checked claims, text like this was most "
                       f"often rated {top} (p={inp.class_probabilities[top]:.2f}). This alone is not evidence.")

    components = [
        {"name": "Evidence retrieval (E)", "value": round(E, 3), "weight": W_E, "available": bool(relevant),
         "detail": e_detail},
        {"name": "Content classification (C)", "value": round(C, 3), "weight": W_C,
         "available": bool(inp.class_probabilities and inp.classifier_in_domain), "detail": c_detail},
        {"name": "Source information (S)", "value": round(S, 3), "weight": W_S,
         "available": inp.source_is_fact_checker, "detail": s_detail},
    ]
    return RiskOutput(level, round(risk, 1), es, es_label, summary, reasons, missing, components)

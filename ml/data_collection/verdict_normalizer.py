"""Map publisher-specific verdict language onto the shared ``Verdict`` schema.

Indian fact-checkers (Factly, Alt News) mostly do not publish a machine-readable
rating. The verdict is written in prose: the headline ("... is a deepfake") and
the conclusion ("To sum up, the video is old and unrelated").

We use an ORDERED list of transparent regex rules. Order matters:

1. Manipulation (deepfake / AI-generated / morphed / doctored)  -> FALSE
2. Old content re-shared as new                                   -> OUTDATED
3. Real content with wrong context (unrelated, scripted, ...)     -> MISLEADING
4. Generic falsity (fake, false, hoax, never said)                -> FALSE
5. Explicit lack of evidence                                       -> INSUFFICIENT_EVIDENCE
6. Explicitly unverifiable                                         -> UNVERIFIED
7. Explicit confirmation ("the claim is true")                     -> TRUE

If nothing matches we return ``None``: we never guess. Every match returns the
rule name so a human can audit why a record got its label.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .schema import Verdict

_NEG = re.compile(r"\b(not|no|never|isn't|aren't|wasn't|weren't|nor)\b[^.]{0,15}$", re.I)


@dataclass(frozen=True)
class Rule:
    name: str
    verdict: Verdict
    pattern: re.Pattern
    check_negation: bool = False


def _r(p: str) -> re.Pattern:
    return re.compile(p, re.I | re.U)


RULES: list[Rule] = [
    # 0. explicit "NOT manipulated" (e.g. "The video is NOT a deepfake") -> genuine content
    Rule("en_not_manipulated", Verdict.TRUE, _r(
        r"\b(is|are|was|were) not (a |an )?(deep\s?fake|ai[-\s]?generated|edited|doctored|morphed|fake)\b")),
    # 1. manipulated media
    Rule("en_manipulated", Verdict.FALSE, _r(
        r"\b(deep\s?fakes?|ai[-\s]?(generated|manipulated|created|made|altered|edited)|"
        r"morphed|doctored|digitally (altered|edited|created|manipulated)|photoshopped|"
        r"fabricated|cloned voice|voice[-\s]?clone|edited (video|image|photo|clip)|(is|are) edited)\b"),
        check_negation=True),
    Rule("hi_manipulated", Verdict.FALSE, _r(r"(डीपफ़ेक|डीपफेक|मॉर्फ|एडिटेड|एडिट की|एडिट किया|AI\s?(से|द्वारा|जनरेटेड|निर्मित))")),
    Rule("kn_manipulated", Verdict.FALSE, _r(r"(ಡೀಪ್\s?‌?ಫೇಕ್|ಎಡಿಟ್|ಮಾರ್ಫ್|AI[-\s]?(ಬಳಸಿ|ಜನರೇಟೆಡ್|ಜಿನರೇಟೆಡ್|ಆಗಿದೆ|ವಿಡಿಯೋ|ವೀಡಿಯೊ))")),
    # 2. outdated
    Rule("en_outdated", Verdict.OUTDATED, _r(
        r"\b(old|older|outdated|years?[-\s]old|dated),?\s+(and\s+)?(\w+,?\s+)?(video|image|photo|clip|picture|"
        r"visuals?|footage|news|report|post|letter|notice|circular|incident|photographs?)s?\b|"
        r"\boutdated\b|\bshared as recent\b|\bpredates?\b")),
    Rule("hi_outdated", Verdict.OUTDATED, _r(r"(पुराना|पुरानी|पुराने|पुरानी तस्वीर|हालिया बताकर)")),
    Rule("kn_outdated", Verdict.OUTDATED, _r(r"(ಹಳೆಯ|ಹಳೇ|(19|20)\d\dರ\s?(ವಿಡಿಯೋ|ವೀಡಿಯೊ|ಫೋಟೋ|ಚಿತ್ರ))")),
    # 3. missing context / miscaptioned
    Rule("en_misleading", Verdict.MISLEADING, _r(
        r"\b(misleading|mislead|out of context|missing context|lacks? context|unrelated|"
        r"scripted|staged|satirical|satire|miscaptioned|misrepresent\w*|misattributed|"
        r"partly (true|false)|half[-\s]truth|clipped|cropped|selectively|"
        r"(do|does|did) not (show|depict)|not from|has no connection|is from (a|an|another|the)\b|"
        r"none of (these|the|this)\b|(falsely |wrongly )?(shared|linked|passed off|attributed|attributing|viral) "
        r"(as|to|with (false|communal|misleading))\b|communal (spin|angle))|,\s*not\s+(a|an|the|from|of|in|during|by)?\s?\w")),
    Rule("hi_misleading", Verdict.MISLEADING, _r(r"(भ्रामक|गुमराह|संदर्भ|असंबंधित|स्क्रिप्टेड|अधूरा|अधूरी|छूट गया|से जोड़कर|जोड़कर|बताकर|दावे के साथ (वायरल|शेयर)|सांप्रदायिक (ऐंगल|एंगल|रंग))")),
    Rule("kn_misleading", Verdict.MISLEADING, _r(r"(ಅಸಂಬಂಧಿತ|ದಾರಿತಪ್ಪಿಸುವ|ತಪ್ಪುದಾರಿಗೆಳೆಯುವ|ಸಂಬಂಧವಿಲ್ಲ|ಸಂಬಂಧವಿಲ್ಲದ|ಸ್ಕ್ರಿಪ್ಟೆಡ್|ಸ್ಕ್ರಿಪ್ಟ್|ಲಿಂಕ್ ಮಾಡಿ|ತೋರಿಸುತ್ತಿಲ್ಲ|ಚಿತ್ರಿಸುವುದಿಲ್ಲ)")),
    # 4. generic false
    Rule("en_false", Verdict.FALSE, _r(
        r"\b(fake|false|falsely|hoax|baseless|bogus|untrue|not true|incorrect|wrong claim|"
        r"no such|did not (say|make|issue|announce|post|write)|didn't say|never said|"
        r"(has|have) not (said|announced|issued|made|been (passed|approved|announced|issued|implemented)))\b")),
    Rule("hi_false", Verdict.FALSE, _r(r"(फ़र्ज़ी|फर्जी|फ़र्जी|झूठ|झूठा|झूठी|ग़लत|गलत|फ़ेक|फेक|बेबुनियाद|नहीं कहा|अफ़वाह|अफवाह)")),
    Rule("kn_false", Verdict.FALSE, _r(r"(ಸುಳ್ಳು|ಸುಳ್ಳಾಗಿ|ನಕಲಿ|ಫೇಕ್|ತಪ್ಪಾಗಿ|ತಪ್ಪು ಮಾಹಿತಿ|ಸತ್ಯವಲ್ಲ|ಸತ್ಯವಿಲ್ಲ|ನೀಡಿಲ್ಲ|"
                                                  r"ಜಾರಿಗೊಳಿಸಿಲ್ಲ|ಹೇಳಿಲ್ಲ|\sಅಲ್ಲ(\s|,|\.|$))")),
    # Kannada "is being shared as ..." with no stronger signal -> context problem
    Rule("kn_shared_as", Verdict.MISLEADING, _r(r"(ಎಂದು|ಎಂಬಂತೆ)\s?ಹಂಚಿಕೊಳ್ಳಲಾಗ")),
    # 5/6. insufficient / unverified
    Rule("en_insufficient", Verdict.INSUFFICIENT_EVIDENCE, _r(
        r"\b(no evidence|lacks? evidence|insufficient evidence|no proof|no credible (evidence|source))\b")),
    Rule("en_unverified", Verdict.UNVERIFIED, _r(
        r"\b(unverified|could not (be )?(independently )?verif\w*|cannot (be )?verif\w*|not (been )?confirmed|unconfirmed)\b")),
    Rule("hi_unverified", Verdict.UNVERIFIED, _r(r"(पुष्टि नहीं|पुष्टि नहीं हो)")),
    # 7. explicit confirmation (checked for negation)
    Rule("en_true", Verdict.TRUE, _r(
        r"\b(claim|it|this|video|image|photo|statement|news|report) (is|are|was) (true|genuine|authentic|correct|accurate|real)\b|"
        r"\b(true|correct|accurate)\s*[.:!]?\s*$"), check_negation=True),
    Rule("hi_true", Verdict.TRUE, _r(r"(दावा सही है|सच है|सही है)"), check_negation=False),
]


def normalize_verdict(*texts: Optional[str]) -> tuple[Optional[Verdict], Optional[str], Optional[str]]:
    """Return ``(verdict, rule_name, matched_text)`` for the first matching rule.

    ``texts`` are searched in order of reliability (e.g. headline first, then
    conclusion). Rules have priority over text order: we look for rule 1 in all
    texts before trying rule 2, so manipulation wins over generic 'false'.
    """
    candidates = [t for t in texts if t]
    for rule in RULES:
        for text in candidates:
            m = rule.pattern.search(text)
            if not m:
                continue
            if rule.check_negation and _NEG.search(text[: m.start()]):
                continue
            # Hindi "सही है" is too generic unless no negation follows it
            if rule.name == "hi_true" and "नहीं" in text[m.start(): m.end() + 10]:
                continue
            return rule.verdict, rule.name, m.group(0)
    return None, None, None

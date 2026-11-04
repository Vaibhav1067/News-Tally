"""Verdict normalisation — cases taken from the manual audit (data/metadata/verdict_audit.md)."""
from __future__ import annotations

import pytest

from ml.data_collection.verdict_normalizer import normalize_verdict


@pytest.mark.parametrize("text,expected", [
    ("This viral video of Rajnath Singh criticising the Indian Army is AI-Manipulated", "FALSE"),
    ("This viral video showing a cloudburst is AI-generated", "FALSE"),
    ("BJP MP said X. The video is NOT a deepfake", "TRUE"),  # negated manipulation
    ("Old video of PM Modi's roadshow in Patna falsely shared as showing his recent visit to Nepal", "OUTDATED"),
    ("An old, unrelated video is being shared as visuals from the crash", "OUTDATED"),
    ("This video predates the Hijab pulling incident", "OUTDATED"),
    ("Video of a drone show in Texas is falsely shared as that of Prayagraj Maha Kumbh", "MISLEADING"),
    ("This video is from the Maldives, not Nepal", "MISLEADING"),
    ("Hindu woman asked to get off bus? It's a scripted video", "MISLEADING"),
    ("Viral notice claiming that the BMC will supply unfiltered water is fake", "FALSE"),
    ("President Droupadi Murmu did not make the statement", "FALSE"),
    ("The Bill has not been passed in the Lok Sabha", "FALSE"),
    ("बांग्लादेश के टोल प्लाज़ा में तोड़फोड़ का पुराना वीडियो सांप्रदायिक दावों के साथ वायरल", "OUTDATED"),
    ("तिहाड़ जेल के बाहर होर्डिंग्स की वायरल तस्वीरें असल में एडिटेड हैं", "FALSE"),
    ("चीन की गाड़ियों का भारत में घुसने का दावा भ्रामक", "MISLEADING"),
    ("ಮಹಾರಾಷ್ಟ್ರದ ಹಳೆಯ ಮತ್ತು ಅಸಂಬಂಧಿತ ವೀಡಿಯೊಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳಲಾಗುತ್ತಿದೆ", "OUTDATED"),
    ("ಈ ವೈರಲ್ ವಿಡಿಯೋ AI ಆಗಿದೆ", "FALSE"),
])
def test_known_cases(text, expected):
    verdict, rule, matched = normalize_verdict(text)
    assert verdict is not None and verdict.value == expected, (rule, matched)


@pytest.mark.parametrize("text", [
    "Books in hand, thousands march in Kolkata to protest against attacks on bookstalls",
    "India's Rice Production Rises, but Prices Continue to Climb",
    "",
])
def test_no_guessing(text):
    """Non-fact-check headlines must stay unlabelled instead of being forced into a class."""
    assert normalize_verdict(text)[0] is None


def test_priority_manipulation_over_generic_false():
    v, rule, _ = normalize_verdict("Fake claim: deepfake video of minister viral")
    assert v.value == "FALSE" and rule == "en_manipulated"

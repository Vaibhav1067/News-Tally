"""Very small, transparent keyword topic tagger.

Used ONLY when the publisher did not tag an article with a meaningful
category. Records tagged this way carry ``category_source="keyword_inferred"``
so analyses can separate publisher labels from our heuristics.
"""
from __future__ import annotations

from typing import Optional

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "Health": ["vaccine", "covid", "corona", "cancer", "doctor", "hospital", "medicine", "disease", "virus",
               "health", "cure", "वैक्सीन", "कोरोना", "इलाज", "ಲಸಿಕೆ", "ಕೊರೊನಾ", "ಆರೋಗ್ಯ"],
    "Finance": ["rbi", "bank", "rupee", "note", "₹", "tax", "gst", "loan", "upi", "scheme", "salary", "pension",
                "बैंक", "नोट", "रुपये", "ಬ್ಯಾಂಕ್", "ರೂಪಾಯಿ"],
    "Elections": ["election", "evm", "vote", "voter", "poll", "ballot", "चुनाव", "वोट", "ईवीएम", "ಚುನಾವಣೆ", "ಮತ"],
    "Religion & Communal": ["hindu", "muslim", "mosque", "temple", "church", "christian", "communal", "masjid",
                            "mandir", "हिंदू", "मुस्लिम", "मस्जिद", "मंदिर", "ಹಿಂದೂ", "ಮುಸ್ಲಿಂ", "ದೇವಸ್ಥಾನ"],
    "Defence & Security": ["army", "soldier", "military", "pakistan", "china", "border", "terror", "operation",
                           "सेना", "जवान", "ಸೇನೆ", "ಯೋಧ"],
    "Politics": ["bjp", "congress", "modi", "rahul gandhi", "minister", "cm ", "government", "aap", "party", "mla",
                 "mp ", "भाजपा", "कांग्रेस", "मोदी", "सरकार", "ಬಿಜೆಪಿ", "ಕಾಂಗ್ರೆಸ್", "ಮೋದಿ", "ಸರ್ಕಾರ"],
}


def infer_category(text: str) -> Optional[str]:
    low = f" {text.lower()} "
    scores = {topic: sum(1 for kw in kws if kw in low) for topic, kws in TOPIC_KEYWORDS.items()}
    topic, score = max(scores.items(), key=lambda kv: kv[1])
    return topic if score > 0 else None


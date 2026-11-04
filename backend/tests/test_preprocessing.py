"""Unit tests: cleaning, language detection, dedup, validation, claim extraction."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ml.data_collection.claim_extractor import extract_claim_and_fact, extract_conclusion
from ml.preprocessing.dedup import drop_exact_duplicates, near_duplicate_groups
from ml.preprocessing.language import detect_language
from ml.preprocessing.text_cleaning import WORD_TOKEN_PATTERN, clean_text, extract_urls, model_text
from ml.preprocessing.validation import validate_row


class TestCleaning:
    def test_html_and_whitespace(self):
        assert clean_text("<p>Hello&nbsp;<b>world</b></p>\n\n  ok") == "Hello world ok"

    def test_hindi_preserved(self):
        assert clean_text("  यह   वीडियो पुराना है ") == "यह वीडियो पुराना है"

    def test_zero_width_removed(self):
        assert clean_text("fa​ke") == "fake"

    def test_currency(self):
        assert clean_text("Rs 500 and Rs.2000 and INR 10") == "₹500 and ₹2000 and ₹10"

    def test_urls(self):
        assert extract_urls("see https://example.com/a?b=1, and http://x.in.") == [
            "https://example.com/a?b=1", "http://x.in"]
        assert model_text("Link https://x.com/y") == "link urltoken"

    def test_indic_tokenizer_keeps_whole_words(self):
        assert re.findall(WORD_TOKEN_PATTERN, "प्रदर्शनकारियों पर") == ["प्रदर्शनकारियों", "पर"]

    def test_empty(self):
        assert clean_text("") == "" and clean_text(None) == ""


class TestLanguage:
    def test_english(self):
        r = detect_language("The government has announced a new scheme for farmers across the country")
        assert r.code == "en" and r.supported_by_model

    def test_hindi(self):
        assert detect_language("सरकार ने किसानों के लिए नई योजना की घोषणा की है").code == "hi"

    def test_kannada(self):
        assert detect_language("ಈ ವೀಡಿಯೊ ಹಳೆಯದು ಮತ್ತು ಅಸಂಬಂಧಿತವಾಗಿದೆ").code == "kn"

    def test_mixed_script(self):
        r = detect_language("Breaking news: मोदी सरकार ने announce किया new scheme today for everyone")
        assert r.is_mixed and r.code == "mixed"

    def test_hinglish(self):
        r = detect_language("yeh video sach hai kya bhai, sab log share karo jaldi")
        assert r.code == "hi-Latn" and not r.supported_by_model

    def test_unsupported_script(self):
        r = detect_language("இந்த வீடியோ பழையது")  # Tamil
        assert r.code == "ta" and not r.supported_by_model

    def test_empty_and_symbols(self):
        assert detect_language("").code == "unknown"
        assert detect_language("!!! ??? 123").code == "unknown"


class TestDedup:
    def test_exact(self):
        df = pd.DataFrame({"fact_check_url": ["a", "a", "b", "c"],
                           "claim_text": ["x one", "x one", "Y  two", "y two"]})
        out, stats = drop_exact_duplicates(df)
        assert len(out) == 2 and stats == {"duplicate_urls": 1, "duplicate_claim_texts": 1}

    def test_near_duplicate_groups(self):
        g = near_duplicate_groups(["Old video of flood in Assam shared as Kerala",
                                   "Old video of floods in Assam shared as Kerala",
                                   "PM Modi did not announce free laptops"])
        assert g[0] == g[1] != g[2]
        assert isinstance(g, np.ndarray)


class TestValidation:
    def test_valid(self):
        assert validate_row({"claim_id": "a", "claim_text": "A long enough claim", "fact_check_url": "https://x.in/a",
                             "publisher": "P", "verdict": "FALSE", "publication_date": "2025-01-01"}) == []

    def test_invalid(self):
        errs = validate_row({"claim_id": "a", "claim_text": "short", "fact_check_url": "notaurl",
                             "publisher": "", "verdict": "PANTS", "publication_date": "yesterday"})
        assert {"missing:publisher", "invalid_url", "invalid_verdict:PANTS", "claim_too_short",
                "invalid_date"} <= set(errs)


class TestClaimExtraction:
    BODY = ("A video is viral. Claim: The video shows police firing in Delhi. Fact: The video is from "
            "Bangladesh and unrelated. More text here. To sum up, the video is from Bangladesh.")

    def test_claim_and_fact(self):
        claim, fact = extract_claim_and_fact(self.BODY)
        assert claim == "The video shows police firing in Delhi."
        assert fact.startswith("The video is from Bangladesh")

    def test_conclusion(self):
        assert extract_conclusion(self.BODY) == "the video is from Bangladesh."

    def test_missing(self):
        assert extract_claim_and_fact("no structure here") == (None, None)

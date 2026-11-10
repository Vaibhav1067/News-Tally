"""API integration + edge-case tests (English, Hindi, mixed, short, long, URLs, no-match, ambiguous)."""
from __future__ import annotations

import pytest

from app.services.extraction import ExtractionError, fetch_url
from app.services.source_service import normalize_domain
from conftest import requires_models


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_empty_input_rejected(client):
    r = client.post("/api/analyze", json={})
    assert r.status_code == 422
    r = client.post("/api/analyze", json={"text": "   "})
    assert r.status_code == 422


def test_invalid_url_rejected(client):
    r = client.post("/api/analyze", json={"url": "not a url"})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "url"


def test_text_too_long_rejected(client):
    assert client.post("/api/analyze", json={"text": "a " * 6000}).status_code == 422


def test_body_size_limit(client):
    r = client.post("/api/analyze", content=b"x" * 70_000, headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_ssrf_blocked():
    for url in ("http://127.0.0.1:8000/api/health", "http://localhost/", "http://169.254.169.254/latest", "ftp://x.com"):
        with pytest.raises(ExtractionError):
            fetch_url(url)


def test_private_url_via_api(client):
    r = client.post("/api/analyze", json={"url": "http://127.0.0.1:9/"})
    assert r.status_code == 422 and "private or local" in r.json()["detail"]


def test_domain_normalisation():
    assert normalize_domain("https://www.NDTV.com/india/x") == "ndtv.com"
    assert normalize_domain("m.altnews.in") == "m.altnews.in"
    assert normalize_domain("") is None


@requires_models
class TestAnalyze:
    def analyze(self, client, **body):
        r = client.post("/api/analyze", json=body)
        assert r.status_code == 200, r.text
        return r.json()

    def test_english_known_claim(self, client):
        d = self.analyze(client, text="Viral video shows Defence Minister Rajnath Singh criticising the Indian Army "
                                      "amid the India-China standoff in Arunachal Pradesh")
        assert d["detected_language"]["code"] == "en"
        assert d["matching_fact_checks"][0]["match_strength"] == "strong"
        assert d["risk_assessment"]["level"] == "HIGH MISINFORMATION RISK"
        assert d["explanation"]["available"] and d["explanation"]["top_features"]
        assert d["stored"] is False

    def test_hindi(self, client):
        d = self.analyze(client, text="दिल्ली पुलिस ने प्रदर्शनकारी महिलाओं की पिटाई की, देखिए यह वीडियो")
        assert d["detected_language"]["code"] == "hi"
        assert d["prediction"]["in_domain"]

    def test_mixed_language(self, client):
        d = self.analyze(client, text="Breaking: मोदी सरकार ने free bijli scheme announce की, share karo sabko")
        assert d["detected_language"]["is_mixed"]

    def test_very_short(self, client):
        d = self.analyze(client, text="hi")
        assert d["risk_assessment"]["level"] == "INSUFFICIENT EVIDENCE"
        assert d["prediction"]["in_domain"] is False

    def test_very_long(self, client):
        d = self.analyze(client, text=("The minister said many things at the rally today. " * 180)[:9500])
        assert d["extracted_content"]["char_count"] <= 10_000

    def test_no_matching_fact_check(self, client):
        d = self.analyze(client, text="My neighbour's cat learned to open the fridge door by itself last Tuesday morning")
        assert d["risk_assessment"]["level"] in ("UNVERIFIED", "INSUFFICIENT EVIDENCE")
        assert all(m["match_strength"] != "strong" for m in d["matching_fact_checks"])

    def test_ambiguous_claim_not_high_risk(self, client):
        d = self.analyze(client, text="Prices of vegetables have gone up a lot this year in many cities")
        assert d["risk_assessment"]["level"] != "HIGH MISINFORMATION RISK"

    def test_unsupported_language(self, client):
        d = self.analyze(client, text="இந்த வீடியோ சென்னையில் எடுக்கப்பட்டது அல்ல, இது பழைய வீடியோ ஆகும்")
        assert d["detected_language"]["code"] == "ta"
        assert d["prediction"]["in_domain"] is False

    def test_currency_variant_retrieval(self, client):
        d = self.analyze(client, text="RBI has asked banks to stop giving Rs 500 notes from ATMs")
        assert any("500" in (m["title"] or "") for m in d["matching_fact_checks"][:3])

    def test_history_opt_in_and_feedback(self, client):
        d1 = self.analyze(client, text="Private claim that should not be stored anywhere at all")
        d2 = self.analyze(client, text="Claim the user chose to save to history for later", save_to_history=True)
        hist = client.get("/api/history").json()
        ids = [h["id"] for h in hist]
        assert d2["analysis_id"] in ids and d1["analysis_id"] not in ids
        r = client.post("/api/feedback", json={"analysis_id": d1["analysis_id"], "feedback_type": "helpful"})
        assert r.status_code == 201
        assert client.post("/api/feedback", json={"analysis_id": "nope", "feedback_type": "helpful"}).status_code == 404
        assert client.post("/api/feedback", json={"analysis_id": d1["analysis_id"], "feedback_type": "x"}).status_code == 422


@requires_models
def test_fact_checks_listing_and_filters(client):
    r = client.get("/api/fact-checks", params={"language": "hi", "page_size": 5})
    d = r.json()
    assert r.status_code == 200 and d["total"] > 0 and all(i["language"] == "hi" for i in d["items"])
    one = client.get(f"/api/fact-checks/{d['items'][0]['id']}")
    assert one.status_code == 200 and one.json()["original_url"].startswith("https://")
    assert client.get("/api/fact-checks/does-not-exist").status_code == 404
    v = client.get("/api/fact-checks", params={"verdict": "UNPARSED", "page_size": 3}).json()
    assert all(i["verdict"] is None for i in v["items"])
    f = client.get("/api/fact-checks/facets").json()
    assert "Factly" in f["sources"]


@requires_models
def test_statistics_and_models(client):
    s = client.get("/api/statistics").json()
    assert s["total_fact_checks"] == sum(s["verdict_distribution"].values())
    assert "not the prevalence" in s["note"]
    m = client.get("/api/models").json()
    assert m["classifier"]["deployed_model"] and "logistic_regression" in m["comparison"]


def test_rate_limit():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.middleware import RateLimitMiddleware

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, per_minute=2)

    @app.post("/api/analyze")
    def ok():
        return {"ok": True}

    c = TestClient(app)
    codes = [c.post("/api/analyze").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_map_states_and_gazetteer(client):
    from app.services.geo_service import MAP_REGIONS, STATES, states_in
    body = client.get("/api/map").json()
    assert len(body["states"]) == len(STATES) == 36
    assert set(MAP_REGIONS.values()) | {"la"} == set(STATES)
    ranks = sorted(s["rate_rank"] for s in body["states"])
    assert ranks == list(range(1, 37))
    assert sum(s["total_crimes"] for s in body["states"]) == body["crime_source"]["national_total"]
    assert states_in("Old video from Lucknow shared as Kolkata violence") == ["up", "wb"]
    assert states_in("दिल्ली पुलिस ने प्रदर्शनकारियों को रोका") == ["dl"]
    assert states_in("Farmers at the Delhi Chalo march in Punjab") == ["pb"]
    assert states_in("Goat prices rise; Indiana governor speaks") == []

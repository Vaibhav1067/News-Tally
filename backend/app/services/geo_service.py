"""State-level view for the India map.

Two independent things are joined per state, and kept separate in the response:

* ``crime_rate`` / ``total_crimes``: registered cognizable crimes (IPC + SLL) per lakh population in 2023,
  from NCRB "Crime in India 2023". These are fixed published figures, not computed here.
  A high rate partly reflects how readily police register cases, so it is not a safety ranking.
* ``mentions`` / ``recent``: fact-checks in *this* dataset whose headline, claim or conclusion names the
  state or one of its listed cities. Matching is a plain gazetteer lookup, so it can miss places and can
  mis-assign shared names (Punjab and Hyderabad also exist in Pakistan).
"""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FactCheck

CRIME_SOURCE = {
    "name": "NCRB, Crime in India 2023",
    "measure": "Registered cognizable crimes (IPC + SLL) per 1,00,000 population, 2023",
    "url": "https://www.ncrb.gov.in/uploads/files/1CrimeinIndia2023PartI.pdf",
    "table_url": "https://en.wikipedia.org/wiki/List_of_states_and_union_territories_of_India_by_crime_rate",
    "national_rate": 448.3,
    "national_total": 6241569,
}

# code: (name, total crimes 2023, crime rate 2023, aliases). Codes match the map's region ids.
# "dnd" (the merged UT) and "la" (Ladakh) have no region of their own on the map; see MAP_REGIONS.
STATES: dict[str, tuple[str, int, float, list[str]]] = {
    "ap": ("Andhra Pradesh", 184293, 346.3, ["andhra", "visakhapatnam", "vizag", "vijayawada", "tirupati", "amaravati", "आंध्र प्रदेश", "ಆಂಧ್ರ ಪ್ರದೇಶ", "ಆಂಧ್ರಪ್ರದೇಶ"]),
    "ar": ("Arunachal Pradesh", 2941, 187.9, ["arunachal", "itanagar", "tawang", "अरुणाचल"]),
    "as": ("Assam", 64959, 181.3, ["assam", "guwahati", "असम", "ಅಸ್ಸಾಂ"]),
    "br": ("Bihar", 353502, 277.5, ["bihar", "patna", "बिहार", "पटना", "ಬಿಹಾರ"]),
    "ct": ("Chhattisgarh", 115493, 381.2, ["chhattisgarh", "raipur", "bastar", "छत्तीसगढ़", "ಛತ್ತೀಸ್‌ಗಢ"]),
    "ga": ("Goa", 3082, 195.4, ["goa", "panaji", "गोवा", "ಗೋವಾ"]),
    "gj": ("Gujarat", 578879, 806.3, ["gujarat", "ahmedabad", "surat", "vadodara", "rajkot", "गुजरात", "अहमदाबाद", "ಗುಜರಾತ್"]),
    "hr": ("Haryana", 224216, 739.2, ["haryana", "gurugram", "gurgaon", "faridabad", "nuh", "हरियाणा", "ಹರಿಯಾಣ"]),
    "hp": ("Himachal Pradesh", 19987, 267.2, ["himachal", "shimla", "manali", "हिमाचल", "ಹಿಮಾಚಲ"]),
    "jh": ("Jharkhand", 63838, 161.1, ["jharkhand", "ranchi", "jamshedpur", "झारखंड", "ಜಾರ್ಖಂಡ್"]),
    "ka": ("Karnataka", 214234, 315.8, ["karnataka", "bengaluru", "bangalore", "mysuru", "mysore", "mangaluru", "hubballi", "कर्नाटक", "बेंगलुरु", "ಕರ್ನಾಟಕ", "ಬೆಂಗಳೂರು", "ಮೈಸೂರು", "ಮಂಗಳೂರು"]),
    "kl": ("Kerala", 584373, 1631.2, ["kerala", "kochi", "thiruvananthapuram", "kozhikode", "wayanad", "केरल", "ಕೇರಳ"]),
    "mp": ("Madhya Pradesh", 495708, 570.3, ["madhya pradesh", "bhopal", "indore", "ujjain", "gwalior", "मध्य प्रदेश", "मध्यप्रदेश", "भोपाल", "इंदौर", "ಮಧ್ಯಪ್ರದೇಶ", "ಮಧ್ಯ ಪ್ರದೇಶ"]),
    "mh": ("Maharashtra", 596103, 470.4, ["maharashtra", "mumbai", "pune", "nagpur", "nashik", "thane", "महाराष्ट्र", "मुंबई", "पुणे", "ಮಹಾರಾಷ್ಟ್ರ", "ಮುಂಬೈ"]),
    "mn": ("Manipur", 20283, 627.8, ["manipur", "imphal", "मणिपुर", "ಮಣಿಪುರ"]),
    "ml": ("Meghalaya", 3532, 105.2, ["meghalaya", "shillong", "मेघालय"]),
    "mz": ("Mizoram", 4050, 326.3, ["mizoram", "aizawl", "मिजोरम"]),
    "nl": ("Nagaland", 1899, 84.9, ["nagaland", "kohima", "dimapur", "नागालैंड"]),
    "or": ("Odisha", 199954, 431.2, ["odisha", "orissa", "bhubaneswar", "puri", "cuttack", "ओडिशा", "ಒಡಿಶಾ"]),
    "pb": ("Punjab", 69944, 227.1, ["punjab", "amritsar", "ludhiana", "jalandhar", "पंजाब", "ಪಂಜಾಬ್"]),
    "rj": ("Rajasthan", 317480, 390.4, ["rajasthan", "jaipur", "jodhpur", "udaipur", "kota", "ajmer", "राजस्थान", "जयपुर", "ರಾಜಸ್ಥಾನ"]),
    "sk": ("Sikkim", 718, 103.9, ["sikkim", "gangtok", "सिक्किम"]),
    "tn": ("Tamil Nadu", 539651, 701.4, ["tamil nadu", "tamilnadu", "chennai", "coimbatore", "madurai", "तमिलनाडु", "चेन्नई", "ತಮಿಳುನಾಡು", "ಚೆನ್ನೈ"]),
    "tg": ("Telangana", 183644, 481.6, ["telangana", "hyderabad", "तेलंगाना", "हैदराबाद", "ತೆಲಂಗಾಣ", "ಹೈದರಾಬಾದ್"]),
    "tr": ("Tripura", 5002, 120.4, ["tripura", "agartala", "त्रिपुरा"]),
    "up": ("Uttar Pradesh", 793020, 335.3, ["uttar pradesh", "lucknow", "ayodhya", "varanasi", "prayagraj", "kanpur", "noida", "agra", "mathura", "meerut", "gorakhpur", "sambhal", "bareilly", "aligarh", "ghaziabad", "उत्तर प्रदेश", "यूपी", "लखनऊ", "अयोध्या", "वाराणसी", "प्रयागराज", "कानपुर", "संभल", "ಉತ್ತರ ಪ್ರದೇಶ", "ಉತ್ತರಪ್ರದೇಶ", "ಅಯೋಧ್ಯೆ"]),
    "ut": ("Uttarakhand", 34017, 291.3, ["uttarakhand", "dehradun", "haridwar", "haldwani", "kedarnath", "उत्तराखंड", "हरिद्वार", "ಉತ್ತರಾಖಂಡ"]),
    "wb": ("West Bengal", 180272, 181.6, ["west bengal", "bengal", "kolkata", "murshidabad", "sandeshkhali", "howrah", "पश्चिम बंगाल", "बंगाल", "कोलकाता", "ಪಶ್ಚಿಮ ಬಂಗಾಳ", "ಕೋಲ್ಕತ್ತಾ"]),
    "an": ("Andaman and Nicobar Islands", 1873, 464.8, ["andaman", "nicobar", "port blair", "अंडमान"]),
    "ch": ("Chandigarh", 4185, 338.9, ["chandigarh", "चंडीगढ़", "ಚಂಡೀಗಢ"]),
    "dnd": ("Dadra and Nagar Haveli and Daman and Diu", 865, 66.9, ["dadra", "nagar haveli", "daman", "silvassa"]),
    "dl": ("Delhi", 344263, 1602.0, ["delhi", "दिल्ली", "ದೆಹಲಿ", "ದಿಲ್ಲಿ"]),
    "jk": ("Jammu and Kashmir", 29595, 217.0, ["jammu", "kashmir", "srinagar", "pahalgam", "pulwama", "कश्मीर", "जम्मू", "पहलगाम", "ಕಾಶ್ಮೀರ", "ಜಮ್ಮು"]),
    "la": ("Ladakh", 522, 173.4, ["ladakh", "leh", "kargil", "galwan", "लद्दाख", "ಲಡಾಖ್"]),
    "ld": ("Lakshadweep", 127, 184.1, ["lakshadweep", "लक्षद्वीप", "ಲಕ್ಷದ್ವೀಪ"]),
    "py": ("Puducherry", 5065, 305.5, ["puducherry", "pondicherry", "पुडुचेरी"]),
}

# Region ids drawn by the map -> state code. The map's outline predates 2019/2020: it draws Ladakh inside
# Jammu and Kashmir, and Dadra and Nagar Haveli apart from Daman and Diu.
MAP_REGIONS = {**{c: c for c in STATES if c not in ("dnd", "la")}, "dn": "dnd", "dd": "dnd"}

_BLANK_DELHI = re.compile(r"delhi\s+chalo", re.I)  # a march's name, not a place of the event


def _patterns() -> dict[str, re.Pattern]:
    out = {}
    for code, (_, _, _, aliases) in STATES.items():
        latin = [re.escape(a) for a in aliases if a.isascii()]
        other = [re.escape(a) for a in aliases if not a.isascii()]
        parts = []
        if latin:
            parts.append(r"(?<![a-z])(?:" + "|".join(latin) + r")(?![a-z])")
        if other:  # \b is unreliable around Indic combining marks, so match these as substrings
            parts.append("(?:" + "|".join(other) + ")")
        out[code] = re.compile("|".join(parts), re.I)
    return out


_PATTERNS = _patterns()
_cache: dict = {"key": None, "value": None}


def states_in(text: str) -> list[str]:
    """Codes of every state named in the text."""
    t = _BLANK_DELHI.sub(" ", text or "")
    return [code for code, pat in _PATTERNS.items() if pat.search(t)]


def india_map(db: Session, recent_n: int = 5) -> dict:
    total = db.scalar(select(func.count()).select_from(FactCheck)) or 0
    latest = db.scalar(select(func.max(FactCheck.publication_date)))
    key = (total, str(latest), recent_n)
    if _cache["key"] == key:
        return _cache["value"]

    rows = db.execute(
        select(FactCheck.id, FactCheck.title, FactCheck.claim_text, FactCheck.explanation, FactCheck.verdict,
               FactCheck.source_name, FactCheck.publication_date, FactCheck.original_url, FactCheck.language)
        .order_by(FactCheck.publication_date.desc().nulls_last(), FactCheck.id)).all()

    mentions = {c: 0 for c in STATES}
    false_n = {c: 0 for c in STATES}
    recent: dict[str, list] = {c: [] for c in STATES}
    located = 0
    for r in rows:
        codes = states_in(" ".join(x for x in (r.title, r.claim_text, r.explanation) if x))
        located += bool(codes)
        for c in codes:
            mentions[c] += 1
            false_n[c] += r.verdict == "FALSE"
            if len(recent[c]) < recent_n:
                recent[c].append({"id": r.id, "title": r.title or r.claim_text, "verdict": r.verdict,
                                  "source_name": r.source_name, "language": r.language, "original_url": r.original_url,
                                  "publication_date": r.publication_date.isoformat() if r.publication_date else None})

    by_rate = sorted(STATES, key=lambda c: -STATES[c][2])
    states = [{"code": c, "name": STATES[c][0], "total_crimes": STATES[c][1], "crime_rate": STATES[c][2],
               "rate_rank": by_rate.index(c) + 1, "mentions": mentions[c], "false_mentions": false_n[c],
               "recent": recent[c]} for c in STATES]
    value = {"crime_source": CRIME_SOURCE, "map_regions": MAP_REGIONS, "states": states,
             "fact_checks_total": total, "fact_checks_located": located}
    _cache.update(key=key, value=value)
    return value

#!/usr/bin/env python3
"""Agent de veille NLP — Fusionne arXiv et les ressources géolocalisées pour OpenFreeMap."""

import json, requests, re
from datetime import datetime, timezone
from hashlib import md5
from pathlib import Path

ARXIV_API = "http://export.arxiv.org/api/query"
CATEGORIES = ["cs.CL", "cs.AI"]
NOTICES_PATH    = Path("data/notices.json")
RESSOURCES_PATH = Path("data/ressources.json")
OUTPUT_PATH     = Path("data/radar.json")

REGION_COORDS = {
    "Kabylie": (36.7118, 4.0459),
    "Aurès":   (35.5559, 6.1743),
    "Souss":   (30.4278, -9.5981),
    "Global":  (33.5000, 2.0000),
}

def classify(title, abstract):
    t = (title + " " + abstract).lower()
    if any(k in t for k in ["corpus", "dataset", "annotation", "benchmark"]): return "Corpus"
    if any(k in t for k in ["model", "llm", "transformer", "fine-tun"]):       return "Model"
    if any(k in t for k in ["tool", "library", "framework", "pipeline"]):      return "Tool"
    if any(k in t for k in ["workshop", "conference", "call for"]):            return "Event"
    return "Paper"

def detect_region(text):
    t = text.lower()
    if "kabyl" in t or "berber" in t or "amazigh" in t: return "Kabylie"
    if "aurès" in t or "aures" in t or "chaoui" in t:   return "Aurès"
    if "souss" in t or "tachelhit" in t:                return "Souss"
    return "Global"

def fetch_arxiv():
    items = []
    for cat in CATEGORIES:
        params = {"search_query": f"cat:{cat}", "start": 0, "max_results": 15,
                  "sortBy": "submittedDate", "sortOrder": "descending"}
        try:
            r = requests.get(ARXIV_API, params=params, timeout=60)
            for e in re.findall(r"<entry>(.*?)</entry>", r.text, re.DOTALL):
                title   = re.search(r"<title>(.*?)</title>", e, re.DOTALL)
                summary = re.search(r"<summary>(.*?)</summary>", e, re.DOTALL)
                link    = re.search(r"<id>(.*?)</id>", e, re.DOTALL)
                pub     = re.search(r"<published>(.*?)</published>", e, re.DOTALL)
                if not (title and summary and link): continue
                items.append({
                    "title":   re.sub(r"\s+", " ", title.group(1)).strip(),
                    "summary": re.sub(r"\s+", " ", summary.group(1)).strip()[:300],
                    "url":     link.group(1).strip(),
                    "date":    pub.group(1)[:10] if pub else datetime.now().strftime("%Y-%m-%d"),
                })
        except Exception as ex:
            print(f"[WARN] arXiv {cat}: {ex}")
    return items

def load_ressources():
    if not RESSOURCES_PATH.exists():
        return {"total": 0, "sources": [], "counts": {}, "items": []}
    return json.loads(RESSOURCES_PATH.read_text(encoding="utf-8"))

def main():
    arxiv_items = fetch_arxiv()
    ressources = load_ressources()

    notices = []
    
    # 1. Ajout des ressources issues des fichiers Excel dans les notices cartographiables
    for r in ressources.get("items", []):
        notices.append({
            "id": r["id"],
            "title": r["nom"],
            "type": r["type"],
            "region": r.get("region", "Global"),
            "lat": r.get("lat", 33.5),
            "lng": r.get("lng", 2.0),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "author": r.get("source", "Catalogue"),
            "summary": r.get("summary", ""),
            "url": r.get("lien", "")
        })

    # 2. Ajout des articles arXiv
    for i, it in enumerate(arxiv_items):
        region = detect_region(it["title"] + " " + it["summary"])
        lat, lng = REGION_COORDS[region]
        notices.append({
            "id": f"arxiv-{i+1}",
            "title": it["title"],
            "type": classify(it["title"], it["summary"]),
            "region": region,
            "lat": lat,
            "lng": lng,
            "date": it["date"],
            "author": "arXiv",
            "summary": it["summary"],
            "url": it["url"],
        })

    payload = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "notices": {"total": len(notices), "items": notices},
        "ressources": ressources,
    }

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {len(notices)} points (évenements + ressources) prêts pour la carte OpenFreeMap.")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""convert_xlsx_v3.py — Fusionne les 3 XLSX et génère des descriptions trilingues."""

import json, re
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

GENERAL_XLSX    = "nlp_ressources_filtrees.xlsx"
BERBERE_XLSX    = "nlp_berbere_kabyle_ressources.xlsx"
ECOSYSTEME_XLSX = "nlp_depots_datasets_modeles_outils (2).xlsx"
LEXICON         = Path("data/lexicon.json")
OUTPUT          = Path("data/ressources.json")

CATEGORY_KEYS = {
    "Conferences / Evenements": "cat_Conferences",
    "Emplois / Stages / Freelance": "cat_Jobs",
    "Revues scientifiques": "cat_Journals",
    "Dataset Berbère": "cat_Dataset",
    "Dataset Kabyle": "cat_Dataset",
    "Modèle Berbère": "cat_Model",
    "Modèle Kabyle": "cat_Model",
    "Outil/Dépôt Berbère": "cat_Tool",
    "Outil/Dépôt Kabyle": "cat_Tool",
    "Datasets": "cat_Dataset",
    "Modèles": "cat_Model",
    "Outils": "cat_Tool",
    "Institution/Corpus": "cat_Institution",
    "Institution/Recherche": "cat_Institution",
    "Institution/Normalisation": "cat_Institution",
    "Organisation/Dépôt": "cat_Institution",
    "Collection": "cat_Institution",
}

def safe(v, default=""):
    if v is None or (isinstance(v, float) and pd.isna(v)): return default
    s = str(v).strip()
    return s if s and s.lower() != "nan" else default

def cat_key(raw):
    return CATEGORY_KEYS.get(raw, "cat_Tool")

def build_replacements(dictionary):
    return sorted(dictionary.items(), key=lambda kv: -len(kv[0]))

def translate(text, replacements):
    if not text: return ""
    out = text
    for src, dst in replacements:
        out = re.sub(r"\b" + re.escape(src) + r"\b", dst, out, flags=re.IGNORECASE)
    return out

def load_general():
    df = pd.read_excel(GENERAL_XLSX, sheet_name="Toutes_donnees")
    df = df.drop_duplicates(subset=["lien"]).reset_index(drop=True)
    return [{
        "id": f"gen-{i+1:03d}", "source": "general",
        "nom": safe(r["nom"]), "type": safe(r["type"]),
        "langue": safe(r["langue"], "Multilingue"),
        "pays": safe(r["pays"], "International"), "taille": "",
        "description_fr": safe(r["type"]), "lien": safe(r["lien"]),
        "licence": safe(r["open_access"], "Variable"),
        "categorie_raw": safe(r["categorie"]),
    } for i, r in df.iterrows()]

def load_berbere():
    df = pd.read_excel(BERBERE_XLSX, sheet_name="Toutes_ressources")
    df = df.drop_duplicates(subset=["lien"]).reset_index(drop=True)
    return [{
        "id": f"ber-{i+1:03d}", "source": "berbere",
        "nom": safe(r["nom"]), "type": safe(r["type"]),
        "langue": safe(r["langue"], "Berbère"),
        "pays": "International", "taille": safe(r.get("taille")),
        "description_fr": safe(r.get("description")) or safe(r["type"]),
        "lien": safe(r["lien"]), "licence": safe(r.get("licence"), "Variable"),
        "categorie_raw": safe(r["categorie"]),
    } for i, r in df.iterrows()]

def load_ecosysteme():
    df = pd.read_excel(ECOSYSTEME_XLSX, sheet_name="Tous_depots")
    df = df.drop_duplicates(subset=["lien"]).reset_index(drop=True)
    return [{
        "id": f"eco-{i+1:03d}", "source": "ecosysteme",
        "nom": safe(r["nom"]), "type": safe(r["type"]),
        "langue": "Multilingue", "pays": "International", "taille": "",
        "description_fr": safe(r.get("description")) or safe(r["type"]),
        "lien": safe(r["lien"]), "licence": safe(r.get("licence"), "Variable"),
        "categorie_raw": safe(r["type"]),
    } for i, r in df.iterrows()]

def main():
    lexicon = json.loads(LEXICON.read_text(encoding="utf-8"))
    repl_en  = build_replacements(lexicon["fr-en"])
    repl_kab = build_replacements(lexicon["fr-kab"])

    all_raw = load_general() + load_berbere() + load_ecosysteme()

    items, untranslated = [], 0
    for r in all_raw:
        desc_fr  = r["description_fr"]
        desc_en  = translate(desc_fr, repl_en)
        desc_kab = translate(desc_fr, repl_kab)
        kab_ok   = desc_kab.lower() != desc_fr.lower()
        if not kab_ok: untranslated += 1

        items.append({
            "id": r["id"], "source": r["source"], "nom": r["nom"],
            "categorie_key": cat_key(r["categorie_raw"]),
            "categorie_raw": r["categorie_raw"], "type": r["type"],
            "langue": r["langue"], "pays": r["pays"], "taille": r["taille"],
            "lien": r["lien"], "licence": r["licence"],
            "description": {
                "fr": desc_fr, "en": desc_en,
                "kab": desc_kab if kab_ok else desc_fr,
                "kab_auto": kab_ok,
            },
        })

    payload = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total": len(items),
        "sources": [
            {"id": "general",    "label_key": "source_general"},
            {"id": "berbere",    "label_key": "source_berbere"},
            {"id": "ecosysteme", "label_key": "source_ecosysteme"},
        ],
        "counts": {
            "general":    sum(1 for i in items if i["source"] == "general"),
            "berbere":    sum(1 for i in items if i["source"] == "berbere"),
            "ecosysteme": sum(1 for i in items if i["source"] == "ecosysteme"),
        },
        "stats": {"descriptions_total": len(items), "descriptions_untranslated_kab": untranslated},
        "items": items,
    }
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {len(items)} ressources trilingues → {OUTPUT}")
    print(f"     {untranslated} descriptions non traduites en kabyle (fallback FR)")

if __name__ == "__main__":
    main()
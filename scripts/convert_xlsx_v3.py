#!/usr/bin/env python3
"""convert_xlsx_v3.py — Fusionne les 3 XLSX, géolocalise finement les ressources
avec détection ville / état US / pays, et produit un catalogue trilingue."""

import json, re, hashlib
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

GENERAL_XLSX    = "nlp_ressources_filtrees.xlsx"
BERBERE_XLSX    = "nlp_berbere_kabyle_ressources.xlsx"
ECOSYSTEME_XLSX = "nlp_depots_datasets_modeles_outils (2).xlsx"
LEXICON         = Path("data/lexicon.json")
OUTPUT          = Path("data/ressources.json")

# ══════════════════════════════════════════════════════════════
#  1) VILLES DU MONDE — détection prioritaire
# ══════════════════════════════════════════════════════════════
CITY_DB = {
    # ── France ──
    "paris":           (48.8566, 2.3522),
    "marseille":       (43.2965, 5.3698),
    "lyon":            (45.7640, 4.8357),
    "grenoble":        (45.1885, 5.7245),
    "toulouse":        (43.6047, 1.4442),
    "bordeaux":        (44.8378, -0.5792),
    "nancy":           (48.6921, 6.1844),
    "rennes":          (48.1173, -1.6778),
    "orléans":         (47.9029, 1.9093),
    "orleans":         (47.9029, 1.9093),
    "lille":           (50.6292, 3.0573),
    "nice":            (43.7102, 7.2620),
    "strasbourg":      (48.5734, 7.7521),
    # ── Royaume-Uni ──
    "london":          (51.5074, -0.1278),
    "cambridge":       (52.2053, 0.1218),
    "oxford":          (51.7520, -1.2577),
    "edinburgh":       (55.9533, -3.1883),
    "manchester":      (53.4808, -2.2426),
    "brighton":        (50.8225, -0.1372),
    # ── États-Unis ──
    "new york":        (40.7128, -74.0060),
    "nyc":             (40.7128, -74.0060),
    "san francisco":   (37.7749, -122.4194),
    "boston":          (42.3601, -71.0589),
    "seattle":         (47.6062, -122.3321),
    "los angeles":     (34.0522, -118.2437),
    "miami":           (25.7617, -80.1918),
    "chicago":         (41.8781, -87.6298),
    "austin":          (30.2672, -97.7431),
    "houston":         (29.7604, -95.3698),
    "dallas":          (32.7767, -96.7970),
    "philadelphia":    (39.9526, -75.1652),
    "pittsburgh":      (40.4406, -79.9959),
    "washington":      (38.9072, -77.0369),
    "atlanta":         (33.7490, -84.3880),
    "baltimore":       (39.2904, -76.6122),
    "denver":          (39.7392, -104.9903),
    "phoenix":         (33.4484, -112.0740),
    "portland":        (45.5152, -122.6784),
    # ── Canada ──
    "toronto":         (43.6532, -79.3832),
    "montreal":        (45.5017, -73.5673),
    "vancouver":       (49.2827, -123.1207),
    "ottawa":          (45.4215, -75.6972),
    # ── Allemagne / Europe centrale ──
    "berlin":          (52.5200, 13.4050),
    "munich":          (48.1351, 11.5820),
    "hamburg":         (53.5511, 9.9937),
    "vienna":          (48.2082, 16.3738),
    "zurich":          (47.3769, 8.5417),
    "amsterdam":       (52.3676, 4.9041),
    "brussels":        (50.8503, 4.3517),
    "bruxelles":       (50.8503, 4.3517),
    "copenhagen":      (55.6761, 12.5683),
    "stockholm":       (59.3293, 18.0686),
    "helsinki":        (60.1699, 24.9384),
    "oslo":            (59.9139, 10.7522),
    # ── Europe du Sud / Est ──
    "rome":            (41.9028, 12.4964),
    "milan":           (45.4642, 9.1900),
    "madrid":          (40.4168, -3.7038),
    "barcelone":       (41.3851, 2.1734),
    "barcelona":       (41.3851, 2.1734),
    "lisbonne":        (38.7223, -9.1393),
    "lisbon":          (38.7223, -9.1393),
    "athenes":         (37.9838, 23.7275),
    "athens":          (37.9838, 23.7275),
    "prague":          (50.0755, 14.4378),
    "warsaw":          (52.2297, 21.0122),
    "budapest":        (47.4979, 19.0402),
    "istanbul":        (41.0082, 28.9784),
    # ── Afrique du Nord (focus) ──
    "alger":           (36.7538, 3.0588),
    "algiers":         (36.7538, 3.0588),
    "algeria":         (36.7538, 3.0588),
    "tizi ouzou":      (36.7118, 4.0459),
    "tizi-ouzou":      (36.7118, 4.0459),
    "bejaia":          (36.7511, 5.0567),
    "béjaïa":          (36.7511, 5.0567),
    "batna":           (35.5559, 6.1743),
    "constantine":     (36.3650, 6.6147),
    "oran":            (35.6969, -0.6331),
    "annaba":          (36.9000, 7.7667),
    "bouira":          (36.3738, 3.9020),
    "rabat":           (34.0209, -6.8416),
    "casablanca":      (33.5731, -7.5898),
    "agadir":          (30.4278, -9.5981),
    "marrakech":       (31.6295, -7.9811),
    "fes":             (34.0331, -5.0003),
    "tanger":          (35.7595, -5.8340),
    "tunis":           (36.8065, 10.1815),
    "tripoli":         (32.8872, 13.1913),
    "le caire":        (30.0444, 31.2357),
    "cairo":           (30.0444, 31.2357),
    # ── Asie ──
    "tokyo":           (35.6762, 139.6503),
    "kyoto":           (35.0116, 135.7681),
    "osaka":           (34.6937, 135.5023),
    "seoul":           (37.5665, 126.9780),
    "beijing":         (39.9042, 116.4074),
    "shanghai":        (31.2304, 121.4737),
    "hong kong":       (22.3193, 114.1694),
    "singapour":       (1.3521, 103.8198),
    "singapore":       (1.3521, 103.8198),
    "bangkok":         (13.7563, 100.5018),
    "taipei":          (25.0330, 121.5654),
    "taiwan":          (25.0330, 121.5654),
    "new delhi":       (28.6139, 77.2090),
    "mumbai":          (19.0760, 72.8777),
    "bangalore":       (12.9716, 77.5946),
    "hyderabad":       (17.3850, 78.4867),
    # ── Amérique latine / Océanie ──
    "sao paulo":       (-23.5505, -46.6333),
    "rio de janeiro":  (-22.9068, -43.1729),
    "buenos aires":    (-34.6037, -58.3816),
    "mexico":          (19.4326, -99.1332),
    "santiago":        (-33.4489, -70.6693),
    "sydney":          (-33.8688, 151.2093),
    "melbourne":       (-37.8136, 144.9631),
    "auckland":        (-36.8485, 174.7633),
}

# ══════════════════════════════════════════════════════════════
#  2) ÉTATS AMÉRICAINS — détection secondaire
# ══════════════════════════════════════════════════════════════
US_STATE_DB = {
    "texas":         (31.9686, -99.9018),
    "california":    (36.7783, -119.4179),
    "new york state":(43.0000, -75.0000),
    "massachusetts": (42.4072, -71.3824),
    "washington state": (47.7511, -120.7401),
    "florida":       (27.6648, -81.5158),
    "illinois":      (40.6331, -89.3985),
    "pennsylvania":  (41.2033, -77.1945),
    "maryland":      (39.0458, -76.6413),
    "georgia":       (32.1656, -82.9001),
    "virginia":      (37.4316, -78.6569),
    "ohio":          (40.4173, -82.9071),
    "michigan":      (44.3148, -85.6024),
    "north carolina":(35.7596, -79.0193),
    "colorado":      (39.5501, -105.7821),
    "arizona":       (34.0489, -111.0937),
    "oregon":        (43.8041, -120.5542),
    "new jersey":    (40.0583, -74.4057),
}

# ══════════════════════════════════════════════════════════════
#  3) PAYS — détection tertiaire (capitale ou ville représentative)
# ══════════════════════════════════════════════════════════════
COUNTRY_DB = {
    "france":        (48.8566, 2.3522),
    "royaume-uni":   (51.5074, -0.1278),
    "royaume uni":   (51.5074, -0.1278),
    "uk":            (51.5074, -0.1278),
    "united kingdom":(51.5074, -0.1278),
    "angleterre":    (51.5074, -0.1278),
    "usa":           (38.9072, -77.0369),
    "united states": (38.9072, -77.0369),
    "états-unis":    (38.9072, -77.0369),
    "etats-unis":    (38.9072, -77.0369),
    "us":            (38.9072, -77.0369),
    "canada":        (45.4215, -75.6972),
    "allemagne":     (52.5200, 13.4050),
    "germany":       (52.5200, 13.4050),
    "espagne":       (40.4168, -3.7038),
    "spain":         (40.4168, -3.7038),
    "italie":        (41.9028, 12.4964),
    "italy":         (41.9028, 12.4964),
    "belgique":      (50.8503, 4.3517),
    "belgium":       (50.8503, 4.3517),
    "suisse":        (46.9480, 7.4474),
    "switzerland":   (46.9480, 7.4474),
    "pays-bas":      (52.3676, 4.9041),
    "netherlands":   (52.3676, 4.9041),
    "portugal":      (38.7223, -9.1393),
    "grèce":         (37.9838, 23.7275),
    "grece":         (37.9838, 23.7275),
    "greece":        (37.9838, 23.7275),
    "suède":         (59.3293, 18.0686),
    "suede":         (59.3293, 18.0686),
    "sweden":        (59.3293, 18.0686),
    "norvège":       (59.9139, 10.7522),
    "norvege":       (59.9139, 10.7522),
    "norway":        (59.9139, 10.7522),
    "danemark":      (55.6761, 12.5683),
    "denmark":       (55.6761, 12.5683),
    "finlande":      (60.1699, 24.9384),
    "finland":       (60.1699, 24.9384),
    "autriche":      (48.2082, 16.3738),
    "austria":       (48.2082, 16.3738),
    "pologne":       (52.2297, 21.0122),
    "poland":        (52.2297, 21.0122),
    "tchéquie":      (50.0755, 14.4378),
    "czech":         (50.0755, 14.4378),
    "turquie":       (41.0082, 28.9784),
    "turkey":        (41.0082, 28.9784),
    "algérie":       (36.7538, 3.0588),
    "algerie":       (36.7538, 3.0588),
    "algeria":       (36.7538, 3.0588),
    "maroc":         (34.0209, -6.8416),
    "morocco":       (34.0209, -6.8416),
    "tunisie":       (36.8065, 10.1815),
    "tunisia":       (36.8065, 10.1815),
    "égypte":        (30.0444, 31.2357),
    "egypte":        (30.0444, 31.2357),
    "egypt":         (30.0444, 31.2357),
    "chine":         (39.9042, 116.4074),
    "china":         (39.9042, 116.4074),
    "japon":         (35.6762, 139.6503),
    "japan":         (35.6762, 139.6503),
    "corée":         (37.5665, 126.9780),
    "coree":         (37.5665, 126.9780),
    "korea":         (37.5665, 126.9780),
    "inde":          (28.6139, 77.2090),
    "india":         (28.6139, 77.2090),
    "australie":     (-33.8688, 151.2093),
    "australia":     (-33.8688, 151.2093),
    "brésil":        (-23.5505, -46.6333),
    "bresil":        (-23.5505, -46.6333),
    "brazil":        (-23.5505, -46.6333),
    "mexique":       (19.4326, -99.1332),
    "mexico":        (19.4326, -99.1332),
    "taiwan":        (25.0330, 121.5654),
}

# ══════════════════════════════════════════════════════════════
#  4) HUBS INTERNATIONAUX — fallback déterministe
#     (au lieu d'entasser tout dans un seul point)
# ══════════════════════════════════════════════════════════════
INTL_HUBS = [
    (48.8566, 2.3522),    # Paris
    (51.5074, -0.1278),   # London
    (40.7128, -74.0060),  # New York
    (37.7749, -122.4194), # San Francisco
    (52.5200, 13.4050),   # Berlin
    (35.6762, 139.6503),  # Tokyo
    (1.3521, 103.8198),   # Singapore
    (-33.8688, 151.2093), # Sydney
    (43.6532, -79.3832),  # Toronto
    (55.6761, 12.5683),   # Copenhagen
    (52.3676, 4.9041),    # Amsterdam
    (25.0330, 121.5654),  # Taipei
    (34.0209, -6.8416),   # Rabat
    (36.7538, 3.0588),    # Alger
    (30.0444, 31.2357),   # Le Caire
    (28.6139, 77.2090),   # New Delhi
    (-23.5505, -46.6333), # São Paulo
    (19.4326, -99.1332),  # Mexico
    (59.3293, 18.0686),   # Stockholm
    (50.8503, 4.3517),    # Bruxelles
]

# ══════════════════════════════════════════════════════════════
#  MAPPINGS catégories / types
# ══════════════════════════════════════════════════════════════
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

TYPE_MAP = {
    "cat_Dataset": "Corpus",
    "cat_Model": "Model",
    "cat_Tool": "Tool",
    "cat_Conferences": "Event",
    "cat_Journals": "Paper",
    "cat_Jobs": "Event",
    "cat_Institution": "Tool",
}


def safe(v, default=""):
    if v is None or (isinstance(v, float) and pd.isna(v)): return default
    s = str(v).strip()
    return s if s and s.lower() != "nan" else default


def cat_key(raw):
    return CATEGORY_KEYS.get(raw, "cat_Tool")


# ══════════════════════════════════════════════════════════════
#  DÉTECTION DE LOCALISATION — 4 niveaux
# ══════════════════════════════════════════════════════════════
def detect_geo_v2(nom, type_str, description, pays, item_id):
    """
    Ordre de priorité :
      1. Ville explicite dans le texte (Paris, Austin, Toronto…)
      2. État américain (Texas, Californie…)
      3. Pays (France, Canada…)
      4. Fallback → hub international déterministe (hash de l'ID)
    Retourne (region, city, lat, lng)
    """
    text = " ".join([str(nom or ""), str(type_str or ""),
                     str(description or ""), str(pays or "")]).lower()

    # Cas spécial berbère/kabyle prioritaire (plus spécifique qu'une ville)
    if any(k in text for k in ["kabyl", "taqbaylit", "kab)"]):
        return ("Kabylie", "Tizi Ouzou", 36.7118, 4.0459)
    if any(k in text for k in ["aurès", "aures", "chaoui"]):
        return ("Aurès", "Batna", 35.5559, 6.1743)
    if any(k in text for k in ["souss", "tachelhit", "tamazight du sud"]):
        return ("Souss", "Agadir", 30.4278, -9.5981)

    # 1. Ville explicite (recherche par mot entier, insensible à la casse)
    for city, (lat, lng) in CITY_DB.items():
        if re.search(r"\b" + re.escape(city) + r"\b", text):
            region = _region_for_city(city)
            return (region, city.title(), lat, lng)

    # 2. État américain
    for state, (lat, lng) in US_STATE_DB.items():
        if re.search(r"\b" + re.escape(state) + r"\b", text):
            return ("Amérique du Nord", state.title() + ", USA", lat, lng)

    # 3. Pays
    for country, (lat, lng) in COUNTRY_DB.items():
        if re.search(r"\b" + re.escape(country) + r"\b", text):
            return (_region_for_country(country), _capital_for(country), lat, lng)

    # 4. Fallback : hub international déterministe
    idx = int(hashlib.md5(str(item_id).encode()).hexdigest(), 16) % len(INTL_HUBS)
    lat, lng = INTL_HUBS[idx]
    hub_name = ["Paris", "London", "New York", "San Francisco", "Berlin",
                "Tokyo", "Singapore", "Sydney", "Toronto", "Copenhagen",
                "Amsterdam", "Taipei", "Rabat", "Alger", "Cairo",
                "New Delhi", "São Paulo", "Mexico", "Stockholm", "Bruxelles"][idx]
    return ("International", hub_name, lat, lng)


def _region_for_city(city):
    """Associe une ville à sa grande région pour le filtre."""
    europe_w = {"paris","london","cambridge","oxford","edinburgh","manchester","brighton",
                "berlin","munich","hamburg","vienna","zurich","amsterdam","brussels",
                "bruxelles","copenhagen","stockholm","helsinki","oslo","lyon","grenoble",
                "toulouse","bordeaux","nancy","rennes","orléans","orleans","lille","nice",
                "strasbourg"}
    europe_s = {"rome","milan","madrid","barcelone","barcelona","lisbonne","lisbon",
                "athenes","athens","prague","warsaw","budapest","istanbul"}
    na = {"new york","nyc","san francisco","boston","seattle","los angeles","miami",
          "chicago","austin","houston","dallas","philadelphia","pittsburgh","washington",
          "atlanta","baltimore","denver","phoenix","portland","toronto","montreal",
          "vancouver","ottawa"}
    asia = {"tokyo","kyoto","osaka","seoul","beijing","shanghai","hong kong",
            "singapour","singapore","bangkok","taipei","taiwan","new delhi",
            "mumbai","bangalore","hyderabad"}
    africa = {"alger","algiers","algeria","tizi ouzou","tizi-ouzou","bejaia","béjaïa",
              "batna","constantine","oran","annaba","bouira","rabat","casablanca",
              "agadir","marrakech","fes","tanger","tunis","tripoli","le caire","cairo"}
    if city in europe_w: return "Europe de l'Ouest"
    if city in europe_s: return "Europe du Sud"
    if city in na:       return "Amérique du Nord"
    if city in asia:     return "Asie"
    if city in africa:   return "Afrique du Nord"
    return "Autres"


def _region_for_country(country):
    eu = {"france","royaume-uni","royaume uni","uk","united kingdom","angleterre",
          "allemagne","germany","espagne","spain","italie","italy","belgique","belgium",
          "suisse","switzerland","pays-bas","netherlands","portugal","grèce","grece",
          "greece","suède","suede","sweden","norvège","norvege","norway","danemark",
          "denmark","finlande","finland","autriche","austria","pologne","poland",
          "tchéquie","czech","turquie","turkey"}
    na = {"usa","united states","états-unis","etats-unis","us","canada","mexique","mexico"}
    afr = {"algérie","algerie","algeria","maroc","morocco","tunisie","tunisia","égypte","egypte","egypt"}
    asia = {"chine","china","japon","japan","corée","coree","korea","inde","india","taiwan"}
    oc = {"australie","australia"}
    sa = {"brésil","bresil","brazil"}
    if country in eu:  return "Europe"
    if country in na:  return "Amérique du Nord"
    if country in afr: return "Afrique du Nord"
    if country in asia:return "Asie"
    if country in oc:  return "Océanie"
    if country in sa:  return "Amérique du Sud"
    return "International"


def _capital_for(country):
    """Nom de la capitale (pour l'affichage)."""
    m = {
        "france":"Paris","royaume-uni":"Londres","royaume uni":"Londres","uk":"Londres",
        "united kingdom":"Londres","angleterre":"Londres","usa":"Washington",
        "united states":"Washington","états-unis":"Washington","etats-unis":"Washington",
        "us":"Washington","canada":"Ottawa","allemagne":"Berlin","germany":"Berlin",
        "espagne":"Madrid","spain":"Madrid","italie":"Rome","italy":"Rome",
        "belgique":"Bruxelles","belgium":"Bruxelles","suisse":"Berne","switzerland":"Berne",
        "pays-bas":"Amsterdam","netherlands":"Amsterdam","portugal":"Lisbonne",
        "grèce":"Athènes","grece":"Athènes","greece":"Athènes","suède":"Stockholm",
        "suede":"Stockholm","sweden":"Stockholm","norvège":"Oslo","norvege":"Oslo",
        "norway":"Oslo","danemark":"Copenhague","denmark":"Copenhague",
        "finlande":"Helsinki","finland":"Helsinki","autriche":"Vienne","austria":"Vienne",
        "pologne":"Varsovie","poland":"Varsovie","tchéquie":"Prague","czech":"Prague",
        "turquie":"Istanbul","turkey":"Istanbul","algérie":"Alger","algerie":"Alger",
        "algeria":"Alger","maroc":"Rabat","morocco":"Rabat","tunisie":"Tunis",
        "tunisia":"Tunis","égypte":"Le Caire","egypte":"Le Caire","egypt":"Le Caire",
        "chine":"Pékin","china":"Pékin","japon":"Tokyo","japan":"Tokyo",
        "corée":"Séoul","coree":"Séoul","korea":"Séoul","inde":"New Delhi","india":"New Delhi",
        "australie":"Sydney","australia":"Sydney","brésil":"São Paulo","bresil":"São Paulo",
        "brazil":"São Paulo","mexique":"Mexico","mexico":"Mexico","taiwan":"Taipei",
    }
    return m.get(country, country.title())


# ══════════════════════════════════════════════════════════════
#  CHARGEMENT XLSX
# ══════════════════════════════════════════════════════════════
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


# ══════════════════════════════════════════════════════════════
#  TRADUCTION
# ══════════════════════════════════════════════════════════════
def build_replacements(dictionary):
    return sorted(dictionary.items(), key=lambda kv: -len(kv[0]))

def translate(text, replacements):
    if not text: return ""
    out = text
    for src, dst in replacements:
        out = re.sub(r"\b" + re.escape(src) + r"\b", dst, out, flags=re.IGNORECASE)
    return out


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def main():
    repl_en, repl_kab = [], []
    if LEXICON.exists():
        lexicon = json.loads(LEXICON.read_text(encoding="utf-8"))
        repl_en  = build_replacements(lexicon.get("fr-en",  {}))
        repl_kab = build_replacements(lexicon.get("fr-kab", {}))
    else:
        print("[WARN] lexicon.json introuvable — descriptions en FR uniquement.")

    all_raw = load_general() + load_berbere() + load_ecosysteme()
    items = []
    untranslated = 0
    geo_stats = {}   # compteur de régions (debug)

    for r in all_raw:
        desc_fr  = r["description_fr"]
        desc_en  = translate(desc_fr, repl_en)  or desc_fr
        desc_kab = translate(desc_fr, repl_kab) or desc_fr
        kab_ok   = desc_kab.lower() != desc_fr.lower()
        if not kab_ok: untranslated += 1

        ckey = cat_key(r["categorie_raw"])
        mapped_type = TYPE_MAP.get(ckey, "Tool")

        # ⚡ DÉTECTION GÉOGRAPHIQUE PRÉCISE
        region, city, lat, lng = detect_geo_v2(
            r["nom"], r["type"], desc_fr, r["pays"], r["id"]
        )
        geo_stats[region] = geo_stats.get(region, 0) + 1

        items.append({
            "id": r["id"],
            "source": r["source"],
            "nom": r["nom"],
            "title": r["nom"],
            "categorie_key": ckey,
            "categorie_raw": r["categorie_raw"],
            "type": mapped_type,
            "langue": r["langue"],
            "pays": r["pays"],
            "region": region,
            "city": city,
            "lat": lat,
            "lng": lng,
            "taille": r["taille"],
            "lien": r["lien"],
            "url": r["lien"],
            "licence": r["licence"],
            "summary": desc_fr,
            "description": {
                "fr":  desc_fr,
                "en":  desc_en,
                "kab": desc_kab,
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
        "stats": {
            "descriptions_total": len(items),
            "descriptions_untranslated_kab": untranslated,
            "geo_distribution": geo_stats,
        },
        "items": items,
    }
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {len(items)} ressources géolocalisées finement → {OUTPUT}")
    print(f"     {untranslated} descriptions non traduites en kabyle (fallback FR)")
    print(f"     Distribution géographique :")
    for region, n in sorted(geo_stats.items(), key=lambda kv: -kv[1]):
        print(f"       · {region:.<30} {n}")
    print(f"\n     Hubs villes détectées (top 10) :")
    cities = {}
    for it in items:
        cities[it["city"]] = cities.get(it["city"], 0) + 1
    for city, n in sorted(cities.items(), key=lambda kv: -kv[1])[:10]:
        print(f"       · {city:.<30} {n}")


if __name__ == "__main__":
    main()
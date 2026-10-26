"""Collecteur DSpace : dépôts institutionnels des universités (mémoires, thèses, articles).

Cible première : les dépôts des universités de Kabylie, riches en travaux sur la langue
kabyle et les langues berbères (Tizi-Ouzou, Béjaïa, Bouira). La liste des dépôts et des
termes cherchés est dans config/veille.json → « dspace » : en ajouter un ne demande aucun code.

Deux interfaces DSpace sont prises en charge, détectées automatiquement :
  • DSpace 7+ (interface Angular) : API REST  {serveur}/server/api/discover/search/objects
  • DSpace ≤ 6 (JSPUI / XMLUI)   : OpenSearch {base}/open-search/discover?format=atom

La recherche est restreinte aux champs titre / sujet / résumé (sinon le plein texte remonte
des milliers de documents sans rapport), puis chaque notice est re-filtrée localement :
un terme suivi doit apparaître dans son titre, ses mots-clés ou son résumé.

Un dépôt en panne n'empêche pas les autres ; le collecteur n'échoue que si TOUS sont inaccessibles.
"""
from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

import requests

# termes « kabyle » → étiquette de langue kab ; termes berbères généraux → zgh
KAB_TERMS = ("kabyl", "taqbaylit", "القبائل")
DC_TYPE = {"dataset": "Corpus", "software": "Tool", "learning object": "Tool"}


def _txt(s: str | None, limit: int | None = None) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit] if limit else t


def _norm(s: str) -> str:
    """Minuscules sans accents latins usuels (berbère / berbere, amazighe / amaziɣe…)."""
    s = s.lower()
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("ɣ", "g"), ("ḍ", "d"), ("ṭ", "t"), ("ẓ", "z"), ("ɛ", "e")):
        s = s.replace(a, b)
    return s


def _matches(terms: list[str], *texts: str) -> list[str]:
    blob = _norm(" ".join(t for t in texts if t))
    return [t for t in terms if _norm(t).rstrip("*") in blob]


def _field_query(term: str, fields: list[str]) -> str:
    """(dc.title:kabyle OR dc.subject:kabyle OR …) — guillemets si le terme contient une espace."""
    t = f'"{term}"' if " " in term else term
    return "(" + " OR ".join(f"{f}:{t}" for f in fields) + ")"


class _Repo:
    """Accès à un dépôt : choix de l'interface, requêtes HTTP (repli http:// si TLS invalide)."""

    def __init__(self, http, conf: dict):
        self.http, self.c = http, conf
        # « …/home » (page d'accueil DSpace 7) n'est pas une racine d'API ; « …/jspui » en est une
        self.base = re.sub(r"/home$", "", conf["url"].rstrip("/"))
        p = urlsplit(conf["url"])
        self.origin = f"{p.scheme}://{p.netloc}"
        self.verify = conf.get("verify_tls", True)
        if not self.verify:  # option explicite par dépôt (métadonnées publiques en lecture seule)
            requests.packages.urllib3.disable_warnings()
        self.api, self.endpoint = None, None

    def get(self, url: str, params: dict) -> requests.Response:
        try:
            return self._get(url, params)
        except requests.exceptions.SSLError:
            # certificat incomplet (fréquent sur les serveurs universitaires) : repli en HTTP si autorisé
            if self.c.get("tls_fallback_http") and url.startswith("https://"):
                if not getattr(self, "_warned", False):
                    print(f"    [DSpace] {self.c['id']} : certificat TLS invalide → repli en http://")
                    self._warned = True
                return self._get("http://" + url[8:], params)
            raise

    def _get(self, url, params):
        r = self.http.s.get(url, params=params, timeout=self.c.get("timeout", 45), verify=self.verify)
        r.raise_for_status()
        return r

    def detect(self) -> str:
        """Interface du dépôt : « rest7 » ou « opensearch » (forcée par conf['api'] si précisée)."""
        forced = self.c.get("api", "auto")
        cands = []
        if forced in ("auto", "rest7"):
            rest = self.c.get("rest")
            cands += [("rest7", rest)] if rest else [("rest7", f"{self.origin}/server/api"),
                                                     ("rest7", f"{self.base}/server/api")]
        if forced in ("auto", "opensearch"):
            cands += [("opensearch", f"{self.base}/open-search/discover"),
                      ("opensearch", f"{self.base}/open-search/"),
                      ("opensearch", f"{self.origin}/open-search/discover")]
        errors = []
        for api, ep in dict.fromkeys(cands):  # sans doublons, ordre conservé
            try:
                if api == "rest7":
                    r = self.get(f"{ep}/discover/search/objects", {"query": "a", "size": 1, "dsoType": "ITEM"})
                    if "searchResult" in r.text:
                        self.api, self.endpoint = api, ep
                        return api
                else:
                    r = self.get(ep, {"query": "a", "format": "atom", "rpp": 1})
                    if re.search(r"<(feed|rss)\b", r.text[:2000]):
                        self.api, self.endpoint = api, ep
                        return api
                errors.append(f"{ep} : réponse inattendue")
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as ex:
                errors.append(f"{ep} : {type(ex).__name__}")
                if not isinstance(ex, requests.exceptions.SSLError):
                    break  # serveur injoignable : inutile d'essayer les autres chemins
            except Exception as ex:
                errors.append(f"{ep} : {type(ex).__name__}")
        raise RuntimeError("aucune interface DSpace trouvée — " + " ; ".join(errors[:3]))

    # ── DSpace 7+ ──
    def search_rest7(self, query: str, size: int, page: int) -> list[dict]:
        r = self.get(f"{self.endpoint}/discover/search/objects", {
            "query": query, "dsoType": "ITEM", "size": size, "page": page,
            "sort": "dc.date.accessioned,DESC"})
        objs = r.json().get("_embedded", {}).get("searchResult", {}).get("_embedded", {}).get("objects", [])
        out = []
        for o in objs:
            it = o.get("_embedded", {}).get("indexableObject") or {}
            md = it.get("metadata") or {}
            v = lambda k: [x.get("value", "") for x in md.get(k, []) if x.get("value")]  # noqa: E731
            out.append({
                "key": it.get("handle") or it.get("uuid"),
                "title": (v("dc.title") or [""])[0],
                "url": (v("dc.identifier.uri") or [f"{self.origin}/items/{it.get('uuid')}"])[0],
                "authors": v("dc.contributor.author") or v("dc.creator"),
                "advisors": v("dc.contributor.advisor"),
                "abstract": " ".join(v("dc.description.abstract")),
                "subjects": v("dc.subject"),
                "discipline": " ".join(v("dc.identifier.citation") + v("dc.description.degree")),
                "issued": (v("dc.date.issued") or [""])[0],
                "deposited": (v("dc.date.accessioned") or [it.get("lastModified") or ""])[0],
                "dc_type": (v("dc.type") or [""])[0], "language": (v("dc.language.iso") or [""])[0],
            })
        return out

    # ── DSpace ≤ 6 (OpenSearch Atom ou RSS) ──
    def search_opensearch(self, query: str, size: int, page: int) -> list[dict]:
        r = self.get(self.endpoint, {"query": query, "format": "atom", "rpp": size, "start": page * size})
        root = ET.fromstring(r.content)
        local = lambda e: e.tag.rsplit("}", 1)[-1]  # noqa: E731
        out = []
        for e in root.iter():
            if local(e) not in ("entry", "item"):
                continue
            f: dict[str, list[str]] = {}
            link = ""
            for c in e:
                name = local(c)
                if name == "link":
                    link = link or c.get("href") or (c.text or "").strip()
                elif name == "author":
                    f.setdefault("creator", []).append(_txt("".join(c.itertext())))
                else:
                    f.setdefault(name, []).append(_txt("".join(c.itertext())))
            g = lambda k: f.get(k) or []  # noqa: E731
            hdl = re.search(r"handle/(\d+/\d+)", link)
            out.append({
                "key": hdl.group(1) if hdl else link or (g("id") or [""])[0],
                "title": (g("title") or [""])[0], "url": link or (g("id") or [""])[0],
                "authors": g("creator"), "advisors": [],
                "abstract": " ".join(g("summary") + g("description") + g("abstract")),
                "subjects": g("subject"), "discipline": "",
                "issued": (g("date") or [""])[0], "deposited": (g("updated") + g("pubDate") + [""])[0],
                "dc_type": (g("type") or [""])[0], "language": (g("language") or [""])[0],
            })
        return out


def _iso(d: str) -> str | None:
    m = re.match(r"\d{4}(-\d{2}(-\d{2})?)?", d or "")
    if m:
        return m.group(0)
    try:  # date RSS (« Tue, 21 Oct 2026 … »)
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(d).date().isoformat()
    except Exception:
        return None


def collect_dspace(http, cfg, mk, previous: dict | None = None, **_) -> list[dict]:
    d = cfg["dspace"]
    terms: list[str] = d["queries"]
    fields = d.get("fields", ["dc.title", "dc.subject", "dc.description.abstract"])
    size = d.get("page_size", 50)
    out: dict[str, dict] = {}
    failed: list[str] = []
    repos = [r for r in d["repositories"] if r.get("enabled", True)]
    for conf in repos:
        repo = _Repo(http, conf)
        rid = conf["id"]
        try:
            api = repo.detect()
        except Exception as ex:
            print(f"    [DSpace] {rid} inaccessible : {ex}")
            failed.append(rid)
            continue
        # premier passage sur ce dépôt : rattrapage de l'historique (plusieurs pages par terme)
        known = any(k.startswith(f"dspace:{rid}:") for k in (previous or {}))
        pages = d.get("daily_pages", 1) if known else d.get("backfill_pages", 4)
        search = repo.search_rest7 if api == "rest7" else repo.search_opensearch
        n_before, errors = len(out), 0
        for term in terms:
            for page in range(pages):
                q = _field_query(term, fields)
                try:
                    recs = search(q, size, page)
                    if not recs and page == 0 and api == "opensearch":
                        recs = search(term, size, page)  # moteur sans recherche par champ : plein texte + filtre local
                except Exception as ex:
                    print(f"    [DSpace] {rid} « {term} » p.{page} : {type(ex).__name__}: {str(ex)[:120]}")
                    errors += 1
                    break
                for rec in recs:
                    iid = f"dspace:{rid}:{rec['key']}"
                    if not rec["key"] or not rec["title"] or iid in out:
                        continue
                    hits = _matches(terms, rec["title"], " ".join(rec["subjects"]), rec["abstract"])
                    if not hits:
                        continue  # le terme n'est que dans le texte intégral : hors sujet
                    kab = any(k in _norm(" ".join(hits)) for k in KAB_TERMS)
                    authors = rec["authors"]
                    out[iid] = mk(
                        id=iid, title=rec["title"], type=DC_TYPE.get(rec["dc_type"].lower(), "Paper"),
                        source="dspace", url=rec["url"],
                        date_s=_iso(rec["deposited"]) or _iso(rec["issued"]),
                        summary=rec["abstract"] or (rec["discipline"] and f"{rec['dc_type']} — {rec['discipline']}"),
                        author=", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                        extra_text=" ".join(rec["subjects"]) + " " + rec["discipline"],
                        languages=["kab"] if kab else ["zgh"], force_focus=True,
                        geo={"lat": conf["lat"], "lng": conf["lng"], "label": conf.get("city"),
                             "region": conf.get("region", "Kabylie"), "geo_precision": "organisation"}
                        if conf.get("lat") is not None else None,
                        location=conf.get("city"), repository=conf.get("name"),
                        meta={k: v for k, v in {
                            "publisher": conf.get("name"), "dc_type": rec["dc_type"], "year": (rec["issued"] or "")[:4],
                            "discipline": rec["discipline"][:120], "keywords": rec["subjects"][:8],
                            "advisors": rec["advisors"][:3], "language": rec["language"], "matched": hits,
                        }.items() if v})
                if len(recs) < size:
                    break  # dernière page
                time.sleep(d.get("delay_s", 1.5))
            time.sleep(d.get("delay_s", 1.5))
        print(f"    [DSpace] {rid} ({api}) : {len(out) - n_before} notices retenues"
              + (f", {errors} requête(s) en échec" if errors else ""))
        if errors == len(terms):
            failed.append(rid)
    if repos and len(failed) == len(repos):
        raise RuntimeError(f"tous les dépôts DSpace sont inaccessibles ({', '.join(failed)})")
    return list(out.values())

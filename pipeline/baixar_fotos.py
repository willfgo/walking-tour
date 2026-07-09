"""Baixa fotos candidatas do Wikimedia Commons para os POIs de uma cidade.

Uso: python3 baixar_fotos.py <slug>
Salva em cities/<slug>/photos-raw/<poi>-<k>.jpg + photos-manifest.json
(candidatas passam por curadoria visual antes de virar photos/ definitivas).
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "walking-tour-pipeline/1.0 (uso pessoal; contato: willfgo@gmail.com)"}
LICENCAS_OK = ("cc-by", "cc-by-sa", "cc0", "pd", "public domain")

BUSCAS = {
    "dubrovnik": {
        "pile-gate": ["Pile Gate Dubrovnik", "Vrata od Pila"],
        "onofrio": ["Onofrio Fountain Dubrovnik", "Velika Onofrijeva česma"],
        "mosteiro-franciscano": ["Franciscan Monastery cloister Dubrovnik", "Franciscan pharmacy Dubrovnik"],
        "stradun": ["Stradun Dubrovnik", "Placa Dubrovnik street"],
        "sponza": ["Sponza Palace Dubrovnik", "Sponza atrium"],
        "sao-bras": ["Church of St Blaise Dubrovnik", "Sveti Vlaho Dubrovnik"],
        "palacio-reitor": ["Rector's Palace Dubrovnik", "Knežev dvor Dubrovnik atrium"],
        "catedral": ["Dubrovnik Cathedral", "Dubrovnik cathedral interior Titian"],
        "gundulic": ["Gundulić Square Dubrovnik market", "Gundulic monument Dubrovnik"],
        "buza": ["Buža bar Dubrovnik", "Dubrovnik walls sea side cliff"],
        "lovrijenac": ["Fort Lovrijenac", "Lovrijenac Dubrovnik view"],
    },
    "kings-landing": {
        "baia-pile": ["Pile bay Dubrovnik", "Dubrovnik Lovrijenac from sea kayak"],
        "bokar": ["Fort Bokar Dubrovnik", "Bokar fortress walls Dubrovnik"],
        "minceta": ["Minčeta Tower Dubrovnik", "Minceta tower Dubrovnik walls"],
        "rua-dominika": ["Sveti Dominika Dubrovnik street", "Dominican monastery Dubrovnik street"],
        "porto-velho": ["Old port Dubrovnik", "Dubrovnik old harbour"],
        "escadaria-vergonha": ["Jesuit stairs Dubrovnik", "St Ignatius church Dubrovnik staircase"],
    },
    "zagreb": {
        "jelacic": ["Ban Jelačić Square Zagreb", "Trg bana Jelačića"],
        "catedral-zagreb": ["Zagreb Cathedral", "Zagrebačka katedrala"],
        "dolac": ["Dolac Market Zagreb", "Dolac tržnica"],
        "tkalciceva": ["Tkalčićeva Street Zagreb", "Tkalciceva ulica"],
        "porta-pedra": ["Stone Gate Zagreb", "Kamenita vrata Zagreb"],
        "sao-marcos": ["St Mark's Church Zagreb", "Crkva svetog Marka Zagreb roof"],
        "lotrscak": ["Lotrščak Tower Zagreb", "Zagreb funicular uspinjača"],
        "teatro-nacional": ["Croatian National Theatre Zagreb", "HNK Zagreb"],
        "setaliste": ["Strossmayer promenade Zagreb", "Strossmayerovo šetalište Zagreb"],
    },
}


def buscar(termo: str, n: int = 4) -> list[dict]:
    q = urllib.parse.urlencode({
        "action": "query", "format": "json",
        "generator": "search", "gsrsearch": f"filetype:bitmap {termo}",
        "gsrnamespace": 6, "gsrlimit": n,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size",
        "iiurlwidth": 1600,
    })
    req = urllib.request.Request(f"{API}?{q}", headers=UA)
    data = json.load(urllib.request.urlopen(req, timeout=30))
    out = []
    for page in (data.get("query", {}).get("pages", {}) or {}).values():
        ii = (page.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}).get("value") or "").lower().replace(" ", "-")
        if not any(k in lic for k in LICENCAS_OK):
            continue
        if (ii.get("width") or 0) < 800:
            continue
        out.append({
            "title": page.get("title", ""),
            "url": ii.get("thumburl") or ii.get("url"),
            "license": meta.get("LicenseShortName", {}).get("value", ""),
            "artist": _strip_html(meta.get("Artist", {}).get("value", "")),
            "descr": _strip_html(meta.get("ImageDescription", {}).get("value", ""))[:160],
        })
    return out


def _strip_html(s: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", s).strip()


def main() -> int:
    slug = sys.argv[1]
    repo = Path(__file__).resolve().parent.parent
    raw = repo / "cities" / slug / "photos-raw"
    raw.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for poi, termos in BUSCAS[slug].items():
        vistos = set()
        cands = []
        for termo in termos:
            for c in buscar(termo):
                if c["url"] not in vistos:
                    vistos.add(c["url"])
                    cands.append(c)
        for k, c in enumerate(cands[:5], 1):
            dest = raw / f"{poi}-{k}.jpg"
            if dest.exists():
                manifest[dest.name] = c
                continue
            try:
                import time
                time.sleep(2)
                req = urllib.request.Request(c["url"], headers=UA)
                dest.write_bytes(urllib.request.urlopen(req, timeout=60).read())
                manifest[dest.name] = c
                print(f"{dest.name}  [{c['license']}]  {c['title']}")
            except Exception as e:
                print(f"FALHA {poi}-{k}: {e}")
    (raw / "photos-manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(manifest)} candidatas em {raw}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

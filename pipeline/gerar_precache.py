"""Gera cities/<slug>/precache.json: assets do tour + tiles OSM da bbox.

Uso: python3 gerar_precache.py <slug>   (rodar da raiz do repo ou de pipeline/)
"""
import json
import math
import sys
from pathlib import Path

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
ZOOMS = (15, 16, 17)
MARGEM_M = 120


def deg2tile(lat: float, lng: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = math.floor((lng + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = math.floor((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def tiles_para_bbox(pontos: list[tuple[float, float]], margem_m: float = MARGEM_M,
                    zooms: tuple[int, ...] = ZOOMS) -> list[tuple[int, int, int]]:
    """(z, x, y) de todos os tiles que cobrem a bbox dos pontos + margem."""
    lats = [p[0] for p in pontos]
    lngs = [p[1] for p in pontos]
    dlat = margem_m / 111_320.0
    dlng = margem_m / (111_320.0 * math.cos(math.radians(sum(lats) / len(lats))))
    s, n = min(lats) - dlat, max(lats) + dlat
    w, e = min(lngs) - dlng, max(lngs) + dlng
    tiles = []
    for z in zooms:
        x0, y0 = deg2tile(n, w, z)   # canto NW -> menor x, menor y
        x1, y1 = deg2tile(s, e, z)   # canto SE -> maior x, maior y
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                tiles.append((z, x, y))
    return tiles


def montar_precache(city_dir: Path) -> dict:
    city_dir = Path(city_dir)
    slug = city_dir.name
    tour = json.loads((city_dir / "tour.json").read_text(encoding="utf-8"))
    rel = f"cities/{slug}"

    assets = [f"{rel}/tour.json"]
    for poi in tour["pois"]:
        for ph in poi.get("photos", []):
            if (city_dir / ph["file"]).exists():
                assets.append(f"{rel}/{ph['file']}")
        if poi.get("audio") and (city_dir / poi["audio"]).exists():
            assets.append(f"{rel}/{poi['audio']}")
    intro = tour.get("intro") or {}
    if intro.get("audio") and (city_dir / intro["audio"]).exists():
        assets.append(f"{rel}/{intro['audio']}")

    pontos = [(p["lat"], p["lng"]) for p in tour["pois"]]
    tiles = [TILE_URL.format(z=z, x=x, y=y) for z, x, y in tiles_para_bbox(pontos)]
    return {"assets": assets, "tiles": tiles}


def main() -> int:
    slug = sys.argv[1]
    repo = Path(__file__).resolve().parent.parent
    city_dir = repo / "cities" / slug
    pre = montar_precache(city_dir)
    out = city_dir / "precache.json"
    out.write_text(json.dumps(pre, indent=1), encoding="utf-8")
    print(f"{out}: {len(pre['assets'])} assets, {len(pre['tiles'])} tiles")
    return 0


if __name__ == "__main__":
    sys.exit(main())

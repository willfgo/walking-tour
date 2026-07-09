import json
import math
from pathlib import Path

from gerar_precache import deg2tile, tiles_para_bbox, montar_precache


def test_deg2tile_casos_conhecidos():
    # z=0: o mundo inteiro é o tile (0,0)
    assert deg2tile(42.6414, 18.1064, 0) == (0, 0)
    # z=1, origem (0,0): hemisfério leste/sul -> tile (1,1)
    assert deg2tile(-0.0001, 0.0001, 1) == (1, 1)
    # fórmula de referência independente (slippy map)
    lat, lng, z = 42.6414, 18.1064, 16
    n = 2 ** z
    x_ref = math.floor((lng + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y_ref = math.floor((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    assert deg2tile(lat, lng, z) == (x_ref, y_ref)


def test_bbox_com_margem_inclui_vizinhos():
    # um único ponto, margem de 120 m: em z17 deve puxar mais de 1 tile
    tiles = tiles_para_bbox([(42.6414, 18.1064)], margem_m=120, zooms=(17,))
    assert len(tiles) > 1
    zs = {t[0] for t in tiles}
    assert zs == {17}


def test_contagem_tiles_cidade_velha_razoavel():
    # bbox real da Cidade Velha de Dubrovnik: precisa ser cacheável (<400 tiles)
    pois = [(42.64143, 18.10652), (42.64010, 18.10986), (42.64230, 18.11069)]
    tiles = tiles_para_bbox(pois, margem_m=120, zooms=(15, 16, 17))
    assert 3 <= len(tiles) < 400


def test_montar_precache(tmp_path: Path):
    city = tmp_path / "cities" / "teste"
    (city / "photos").mkdir(parents=True)
    (city / "audio").mkdir()
    (city / "photos" / "01-a-1.jpg").write_bytes(b"x")
    (city / "audio" / "01-a.mp3").write_bytes(b"x")
    tour = {
        "city": "Teste",
        "route": [],
        "pois": [{
            "id": "a", "order": 1, "name": "A", "lat": 42.6414, "lng": 18.1064,
            "script": "x", "audio": "audio/01-a.mp3",
            "photos": [{"file": "photos/01-a-1.jpg", "caption": "", "credit": ""}],
            "practical": None, "maps_url": "x", "duration_s": 60,
        }],
    }
    (city / "tour.json").write_text(json.dumps(tour), encoding="utf-8")
    pre = montar_precache(city)
    assert "cities/teste/tour.json" in pre["assets"]
    assert "cities/teste/photos/01-a-1.jpg" in pre["assets"]
    assert "cities/teste/audio/01-a.mp3" in pre["assets"]
    assert all(u.startswith("https://tile.openstreetmap.org/") for u in pre["tiles"])

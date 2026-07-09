import json
from pathlib import Path

from validar_tour import validar


def tour_min(city: Path, **override) -> dict:
    (city / "photos").mkdir(parents=True, exist_ok=True)
    (city / "photos" / "01-a-1.jpg").write_bytes(b"x")
    poi = {
        "id": "a", "order": 1, "name": "A", "lat": 42.64, "lng": 18.10,
        "duration_s": None, "audio": None,
        "script": " ".join(["palavra"] * 150),
        "photos": [{"file": "photos/01-a-1.jpg", "caption": "c", "credit": "cr"}],
        "practical": None, "maps_url": "https://maps.apple.com/?daddr=1,2",
    }
    poi.update(override)
    tour = {"city": "T", "title": "t", "intro": {"text": "x", "audio": None},
            "route": [[42.64, 18.10]], "pois": [poi]}
    (city / "tour.json").write_text(json.dumps(tour), encoding="utf-8")
    return tour


def test_tour_valido_passa(tmp_path):
    tour_min(tmp_path / "c")
    erros = validar(tmp_path / "c")
    assert erros == []


def test_foto_faltando_falha(tmp_path):
    city = tmp_path / "c"
    tour_min(city, photos=[{"file": "photos/nao-existe.jpg", "caption": "", "credit": ""}])
    assert any("nao-existe" in e for e in validar(city))


def test_script_curto_falha(tmp_path):
    city = tmp_path / "c"
    tour_min(city, script="curto demais")
    assert any("script" in e.lower() for e in validar(city))


def test_order_duplicado_falha(tmp_path):
    city = tmp_path / "c"
    t = tour_min(city)
    t["pois"].append({**t["pois"][0], "id": "b", "order": 1})
    (city / "tour.json").write_text(json.dumps(t), encoding="utf-8")
    assert any("order" in e.lower() for e in validar(city))


def test_audio_referenciado_inexistente_falha(tmp_path):
    city = tmp_path / "c"
    tour_min(city, audio="audio/01-a.mp3")
    assert any("01-a.mp3" in e for e in validar(city))

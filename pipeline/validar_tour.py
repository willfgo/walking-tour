"""Valida cities/<slug>/tour.json: schema, arquivos, durações.

Uso: python3 validar_tour.py <slug>  -> exit 0 (ok) / 1 (erros listados)
"""
import json
import subprocess
import sys
from pathlib import Path

OBRIGATORIOS = ("id", "order", "name", "lat", "lng", "script", "audio",
                "photos", "practical", "maps_url")
DUR_MIN_S, DUR_MAX_S = 30, 180
DUR_TOL_S = 5
PALAVRAS_MIN, PALAVRAS_MAX = 100, 300


def _duracao(mp3: Path) -> float | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(mp3)],
            capture_output=True, text=True, check=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return None


def validar(city_dir: Path) -> list[str]:
    city_dir = Path(city_dir)
    erros: list[str] = []
    try:
        tour = json.loads((city_dir / "tour.json").read_text(encoding="utf-8"))
    except Exception as e:
        return [f"tour.json ilegível: {e}"]

    for campo in ("city", "title", "intro", "route", "pois"):
        if campo not in tour:
            erros.append(f"campo raiz faltando: {campo}")
    pois = tour.get("pois", [])
    if not pois:
        erros.append("nenhum POI")

    ids = [p.get("id") for p in pois]
    if len(ids) != len(set(ids)):
        erros.append("ids duplicados")
    orders = sorted(p.get("order", 0) for p in pois)
    if orders != list(range(1, len(pois) + 1)):
        erros.append(f"order não é contíguo 1..{len(pois)}: {orders}")

    for p in pois:
        pid = p.get("id", "?")
        for campo in OBRIGATORIOS:
            if campo not in p:
                erros.append(f"{pid}: campo faltando: {campo}")
        if not isinstance(p.get("lat"), (int, float)) or not isinstance(p.get("lng"), (int, float)):
            erros.append(f"{pid}: lat/lng não numéricos")
        n_palavras = len((p.get("script") or "").split())
        if not (PALAVRAS_MIN <= n_palavras <= PALAVRAS_MAX):
            erros.append(f"{pid}: script com {n_palavras} palavras (esperado {PALAVRAS_MIN}-{PALAVRAS_MAX})")
        for ph in p.get("photos", []):
            if not (city_dir / ph["file"]).exists():
                erros.append(f"{pid}: foto faltando: {ph['file']}")
            if not ph.get("credit"):
                erros.append(f"{pid}: foto sem crédito: {ph['file']}")
        audio = p.get("audio")
        if audio:
            f = city_dir / audio
            if not f.exists():
                erros.append(f"{pid}: áudio faltando: {audio}")
            else:
                dur = _duracao(f)
                if dur is None:
                    erros.append(f"{pid}: áudio ilegível: {audio}")
                elif not (DUR_MIN_S - DUR_TOL_S <= dur <= DUR_MAX_S + DUR_TOL_S):
                    erros.append(f"{pid}: duração {dur:.0f}s fora de {DUR_MIN_S}-{DUR_MAX_S}s")
                dur_decl = p.get("duration_s")
                if dur is not None and dur_decl and abs(dur - dur_decl) > DUR_TOL_S:
                    erros.append(f"{pid}: duration_s={dur_decl} difere do real {dur:.0f}s")
    intro_audio = (tour.get("intro") or {}).get("audio")
    if intro_audio and not (city_dir / intro_audio).exists():
        erros.append(f"intro: áudio faltando: {intro_audio}")
    return erros


def main() -> int:
    slug = sys.argv[1]
    repo = Path(__file__).resolve().parent.parent
    erros = validar(repo / "cities" / slug)
    if erros:
        print(f"INVÁLIDO ({len(erros)} erros):")
        for e in erros:
            print(" -", e)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

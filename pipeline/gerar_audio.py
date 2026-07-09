"""Gera narrações OmniVoice (voz clonada) para os POIs de uma cidade.

Uso: python3 gerar_audio.py <slug> [--poi id] [--intro-only]

Sem fallback `say` (decisão de design: nunca misturar vozes — POI sem áudio
fica como "áudio em preparo" no app). Após cada POI: atualiza tour.json,
regenera precache.json, bumpa a versão do SW e commita+publica (dev:main).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from gerar_precache import montar_precache

OMNI_DIR = Path.home() / "Desktop" / "Claude" / "omnivoice"
OMNIVOICE_BIN = OMNI_DIR / "venv" / "bin" / "omnivoice-infer"
REF_AUDIO = OMNI_DIR / "ref-animada.wav"
REF_TEXT = ("Meu nome é Wilton Gomes, sou cardiologista intervencionista e "
            "trabalha aqui em Curitiba. Todos os dias eu cuido de corações, "
            "uns com infarto, outros com válvulas que já não abrem como deveria.")
PHRASE_TIMEOUT_S = 300
NORM_AR = "24000"
SILENCIO_S = 0.6
REPO = Path(__file__).resolve().parent.parent


def dividir_frases(script: str) -> list[str]:
    frases = []
    for linha in script.splitlines():
        t = linha.strip()
        if not t or t.startswith("#"):
            continue
        frases.append(t)
    return frases


def nome_mp3(order: int, poi_id: str) -> str:
    return f"{order:02d}-{poi_id}.mp3"


def bump_sw_version(sw_src: str) -> tuple[str, str]:
    m = re.search(r'const VERSION = "wt-v(\d+)"', sw_src)
    nova = f"wt-v{int(m.group(1)) + 1}"
    return re.sub(r'const VERSION = "wt-v\d+"', f'const VERSION = "{nova}"', sw_src), nova


def sintetizar_frase(texto: str, out_wav: Path, runner=subprocess.run) -> bool:
    """OmniVoice com 1 retry. SEM fallback say — falhou, retorna False."""
    out_wav = Path(out_wav)
    cmd = [str(OMNIVOICE_BIN), "--text", texto, "--ref_audio", str(REF_AUDIO),
           "--ref_text", REF_TEXT, "--output", str(out_wav),
           "--language", "pt", "--device", "mps"]
    for _ in range(2):
        try:
            runner(cmd, timeout=PHRASE_TIMEOUT_S, check=True, capture_output=True)
            if out_wav.exists() and out_wav.stat().st_size > 0:
                return True
        except Exception:
            continue
    return False


def _ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args],
                   check=True, capture_output=True)


def gerar_poi(script: str, mp3_dest: Path, work: Path, log=print) -> float | None:
    """Sintetiza todas as frases; falhou UMA -> aborta o POI (None)."""
    frases = dividir_frases(script)
    work.mkdir(parents=True, exist_ok=True)
    sil = work / "sil.wav"
    _ffmpeg(["-f", "lavfi", "-i", f"anullsrc=r={NORM_AR}:cl=mono",
             "-t", str(SILENCIO_S), "-c:a", "pcm_s16le", str(sil)])
    segs = []
    for i, frase in enumerate(frases, 1):
        seg = work / f"seg-{i}.wav"
        if not sintetizar_frase(frase, seg):
            log(f"  FALHA na frase {i}/{len(frases)}: {frase[:60]}... — POI abortado")
            return None
        seg_n = work / f"seg-{i}-n.wav"
        _ffmpeg(["-i", str(seg), "-ar", NORM_AR, "-ac", "1",
                 "-c:a", "pcm_s16le", str(seg_n)])
        segs.append(seg_n)
        log(f"  frase {i}/{len(frases)} ok")
    lista = work / "concat.txt"
    linhas = []
    for s in segs:
        linhas.append(f"file '{s}'")
        linhas.append(f"file '{sil}'")
    lista.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    final = work / "final.wav"
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(final)])
    mp3_dest.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg(["-i", str(final), "-c:a", "libmp3lame", "-q:a", "5", "-ac", "1",
             str(mp3_dest)])
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(mp3_dest)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def publicar(slug: str, msg: str) -> None:
    pre = montar_precache(REPO / "cities" / slug)
    (REPO / "cities" / slug / "precache.json").write_text(
        json.dumps(pre, indent=1), encoding="utf-8")
    sw = REPO / "app" / "sw.js"
    novo, versao = bump_sw_version(sw.read_text(encoding="utf-8"))
    sw.write_text(novo, encoding="utf-8")
    subprocess.run(["git", "-C", str(REPO), "add", "cities", "app/sw.js"], check=True)
    subprocess.run(["git", "-C", str(REPO), "commit", "-q", "-m",
                    f"{msg} ({versao})\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"],
                   check=True)
    subprocess.run(["git", "-C", str(REPO), "push", "-q", "origin", "dev:main"], check=True)


def main() -> int:
    slug = sys.argv[1]
    so_poi = sys.argv[sys.argv.index("--poi") + 1] if "--poi" in sys.argv else None
    intro_only = "--intro-only" in sys.argv
    city_dir = REPO / "cities" / slug
    tour_path = city_dir / "tour.json"
    base_work = Path(os.environ.get("CLAUDE_JOB_DIR", tempfile.gettempdir())) / "tmp" / f"audio-{slug}"

    tour = json.loads(tour_path.read_text(encoding="utf-8"))

    fila = []
    if not so_poi and not (tour.get("intro") or {}).get("audio"):
        fila.append(("intro", 0, tour["intro"]["text"]))
    if not intro_only:
        for p in sorted(tour["pois"], key=lambda p: p["order"]):
            if so_poi and p["id"] != so_poi:
                continue
            if not p.get("audio"):
                fila.append((p["id"], p["order"], p["script"]))

    print(f"{len(fila)} narrações na fila")
    for pid, order, script in fila:
        mp3 = nome_mp3(order, pid)
        print(f"[{pid}] gerando {mp3} ({len(dividir_frases(script))} frases)")
        dur = gerar_poi(script, city_dir / "audio" / mp3, base_work / pid)
        if dur is None:
            continue
        # relê o tour (pode ter mudado) e grava
        tour = json.loads(tour_path.read_text(encoding="utf-8"))
        if pid == "intro":
            tour["intro"]["audio"] = f"audio/{mp3}"
        else:
            for p in tour["pois"]:
                if p["id"] == pid:
                    p["audio"] = f"audio/{mp3}"
                    p["duration_s"] = round(dur)
        tour_path.write_text(json.dumps(tour, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        print(f"[{pid}] ok — {dur:.0f}s")
        try:
            publicar(slug, f"feat: áudio {mp3}")
            print(f"[{pid}] publicado")
        except subprocess.CalledProcessError as e:
            print(f"[{pid}] publicação falhou ({e}); áudio salvo localmente")
    print("fila concluída")
    return 0


if __name__ == "__main__":
    sys.exit(main())

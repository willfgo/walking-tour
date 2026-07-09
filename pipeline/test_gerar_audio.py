import json
from pathlib import Path

from gerar_audio import dividir_frases, nome_mp3, bump_sw_version, sintetizar_frase


def test_dividir_frases_ignora_vazias_e_comentarios():
    script = "Primeira frase.\n\n# comentário\nSegunda frase.\n   \nTerceira."
    assert dividir_frases(script) == ["Primeira frase.", "Segunda frase.", "Terceira."]


def test_nome_mp3():
    assert nome_mp3(1, "pile-gate") == "01-pile-gate.mp3"
    assert nome_mp3(11, "lovrijenac") == "11-lovrijenac.mp3"
    assert nome_mp3(0, "intro") == "00-intro.mp3"


def test_bump_sw_version():
    src = 'const VERSION = "wt-v2";\nresto'
    out, nova = bump_sw_version(src)
    assert 'const VERSION = "wt-v3";' in out
    assert nova == "wt-v3"
    assert "resto" in out


def test_sintetizar_frase_sem_fallback_say(tmp_path):
    """Falha do OmniVoice NÃO pode cair para `say` — retorna False."""
    chamadas = []

    def runner_falha(cmd, **kw):
        chamadas.append(cmd)
        raise RuntimeError("omnivoice quebrou")

    ok = sintetizar_frase("Olá.", tmp_path / "seg.wav", runner=runner_falha)
    assert ok is False
    # retry 1x do omnivoice = 2 chamadas, nenhuma delas é `say`
    assert len(chamadas) == 2
    assert all("say" not in str(c[0]) for c in chamadas)


def test_sintetizar_frase_retry_sucesso(tmp_path):
    tentativas = []

    def runner(cmd, **kw):
        tentativas.append(1)
        if len(tentativas) == 1:
            raise RuntimeError("flake")
        Path(cmd[cmd.index("--output") + 1]).write_bytes(b"RIFF")

    ok = sintetizar_frase("Olá.", tmp_path / "seg.wav", runner=runner)
    assert ok is True
    assert len(tentativas) == 2

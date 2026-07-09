# Walking Tour

Guia turístico autoguiado (PWA) — mapa com roteiro a pé, fotos e narração em áudio
na voz clonada do Wilton. Roda no iPhone via Safari, funciona offline depois da
primeira abertura.

**App:** https://willfgo.github.io/walking-tour/

## Como usar no iPhone

1. Abra a URL no Safari (com wifi).
2. Compartilhar → **Adicionar à Tela de Início**.
3. Abra o app uma vez ainda no wifi — o service worker baixa mapa, fotos e áudios.
4. Na rua funciona sem internet. POIs sem áudio ainda mostram o texto ("áudio em preparo");
   recarregue no wifi do hotel para puxar áudios novos.

## Estrutura

- `app/` — app genérico (Leaflet vendorado, service worker, sem build).
- `cities/<slug>/` — dados de cada cidade: `tour.json`, `photos/`, `audio/`, `precache.json`.
- `pipeline/` — roda no Mac: `baixar_fotos.py` (Wikimedia Commons), `gerar_audio.py`
  (OmniVoice → mp3, sem fallback de voz), `gerar_precache.py`, `validar_tour.py`.

## Nova cidade

1. Criar `cities/<slug>/tour.json` (copiar schema de dubrovnik; script = uma frase por linha).
2. `python3 pipeline/baixar_fotos.py <slug>` + curadoria visual → `photos/` + refs no tour.json.
3. `python3 pipeline/validar_tour.py <slug>`.
4. Adicionar o slug em `app/cities.json`, `python3 pipeline/gerar_precache.py <slug>`, bump `VERSION` em `app/sw.js`.
5. Publicar; depois `python3 pipeline/gerar_audio.py <slug>` gera e publica os áudios progressivamente.

Modo "flash": os passos 1–5 sem o `gerar_audio.py` — tour de texto+fotos no ar em minutos.

## Testes

```
python3 -m pytest pipeline/ -q
```

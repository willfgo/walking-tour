# Walking Tour — guia turístico com narração (design)

**Data:** 2026-07-09 · **Status:** aprovado em conversa (piloto Dubrovnik)

## Objetivo

Webapp de walking tour autoguiado que roda no iPhone (Safari/PWA): mapa com roteiro e pontos de interesse (POIs); ao tocar num POI, mostra fotos e toca narração de 30s–3min na voz clonada do Wilton. Piloto: **Dubrovnik (uso 10–12/07/2026)**, desenhado como pipeline reutilizável (cidade = pasta de dados; app = genérico). Segunda cidade: **Zagreb** (12–13/07), gerada com o mesmo pipeline após Dubrovnik.

## Decisões (com o usuário, 09/07)

- **Alvo:** os dois — usar agora na viagem E servir de piloto do pipeline reutilizável.
- **Voz:** OmniVoice local (voz clonada do Wilton, MacBook, ~2min/frase em CPU). **Sem fallback `say`** — áudio ausente exibe "áudio em preparo" + transcrição; nunca misturar vozes.
- **Conectividade:** online + cache offline (PWA com service worker; abre uma vez no wifi, funciona na rua).
- **GPS:** posição no mapa (ponto azul) + toque manual no POI. Sem auto-play por proximidade.
- **Roteiro:** Claude propõe e executa direto (sem gate de aprovação da lista de POIs).
- **Extras aprovados (4):** player melhorado; navegação esperta; info prática por POI; tour de Zagreb depois.

## Arquitetura

**Opção escolhida:** PWA estática hospedada no GitHub Pages. (Descartadas: HTML único auto-contido via Files/Syncthing — áudio base64 pesado e player ruim no iOS; app nativo — overkill/prazo.)

```
~/Desktop/Claude/walking-tour/          # repo git → GitHub Pages
├── app/                                # genérico, não sabe nada de cidade
│   ├── index.html                      # SPA: Leaflet + player + painel POI
│   ├── app.js / app.css
│   ├── sw.js                           # service worker (cache offline)
│   └── manifest.webmanifest            # PWA (Add to Home Screen)
├── cities/
│   ├── dubrovnik/
│   │   ├── tour.json                   # dados do tour (schema abaixo)
│   │   ├── precache.json               # assets p/ o service worker cachear
│   │   ├── audio/NN-slug.mp3           # narrações (mono ~96kbps)
│   │   └── photos/NN-slug-K.jpg        # ~1200px, Wikimedia Commons
│   └── zagreb/                         # fase 2, mesmo formato
├── pipeline/                           # roda no Mac, não é servido
│   ├── gerar_audio.py                  # texto → OmniVoice → concat ffmpeg → mp3
│   ├── baixar_fotos.py                 # Wikimedia Commons → resize + crédito
│   └── validar_tour.py                 # schema + arquivos + durações
└── docs/superpowers/specs/             # este spec
```

URL: `https://{usuario-github}.github.io/walking-tour/?city=dubrovnik` — o usuário GitHub é resolvido na publicação via `gh api user`. Cidade via query param; default = última usada, salva em localStorage.

### Schema `tour.json`

```json
{
  "city": "Dubrovnik",
  "title": "Cidade Velha — walking tour",
  "intro": { "text": "…", "audio": "audio/00-intro.mp3" },
  "route": [[42.64, 18.10]],
  "pois": [{
    "id": "pile-gate", "order": 1, "name": "Portão de Pile",
    "lat": 42.6414, "lng": 18.1064,
    "duration_s": 95,
    "script": "texto integral da narração (transcrição)",
    "audio": "audio/01-pile-gate.mp3",
    "photos": [{ "file": "photos/01-pile-gate-1.jpg", "caption": "…", "credit": "Foto: X / Wikimedia Commons (CC BY-SA)" }],
    "practical": "Ingresso: grátis. Dica: chegue antes das 9h — cruzeiros lotam a partir das 10h.",
    "maps_url": "https://maps.apple.com/?daddr=42.6414,18.1064&dirflg=w"
  }]
}
```

`audio` pode ser `null` enquanto a narração ainda não foi gerada (app mostra "áudio em preparo").

## App (comportamento)

- **Mapa** (Leaflet + tiles OSM): rota desenhada (polyline), marcadores numerados na ordem da caminhada, ponto azul da posição (`watchPosition`, só com app aberto). **Modo lista** alternável: POIs na ordem, com distância/minutos a pé até o próximo (haversine, 4,5 km/h).
- **Painel do POI** (bottom sheet ao tocar marcador ou item da lista): fotos com swipe + crédito, player de áudio com transcrição expansível, bloco "info prática", botão "abrir no Maps", check "visitado" (localStorage).
- **Player:** velocidade 1×/1.25×/1.5×; Wake Lock API para tela acesa durante o tour; metadata via Media Session API (áudio segue com tela bloqueada quando o iOS permitir).
- **Áudio ausente:** badge "áudio em preparo", transcrição legível, sem player.

## Offline (service worker)

- Pré-cache no primeiro load: app shell, `tour.json`, fotos, áudios existentes e **tiles OSM da bounding box do tour** (zoom 15–17; Cidade Velha ≈ poucas centenas de tiles, poucos MB).
- Estratégia cache-first com atualização em background; recarregar no wifi do hotel puxa áudios novos.
- Lista de assets gerada pelo pipeline (`precache.json` por cidade) — o SW não adivinha.

## Conteúdo — Dubrovnik (piloto)

~11 POIs, ordem de caminhada: Pile Gate → Fonte de Onofrio → Mosteiro Franciscano/Farmácia antiga → Stradun → Palácio Sponza → Igreja de São Brás → Palácio do Reitor → Catedral → Praça Gundulić → Bar Buža/muralhas sul → Forte Lovrijenac. Ajustes finos de ordem/inclusão a critério do Claude na execução.

- **Textos:** PT-BR, ~150–250 palavras (~1–2min falado), tom de guia: contexto histórico + 1 detalhe curioso + "o que olhar agora". Escritos por Claude com verificação factual (WebSearch quando necessário).
- **Fotos:** 2–3 por POI, Wikimedia Commons (licença livre), redimensionadas ~1200px, crédito obrigatório na legenda.
- **Áudio:** pipeline OmniVoice por frase (padrão do podcast matinal, `~/.claude/scripts/podcast-matinal/voz.py` como referência) → concat ffmpeg normalizado → mp3 mono ~96kbps. Estimativa 5–6h de CPU para o tour; gerar na ordem da caminhada e publicar progressivamente (commits incrementais → Pages).

## Erros e degradação

- GPS negado → mapa e lista funcionam sem ponto azul.
- Tile faltando offline → mapa parcial; modo lista cobre tudo.
- Áudio faltando → transcrição.
- `tour.json` inválido → mensagem de erro clara (não tela branca).

## Verificação

- `validar_tour.py`: schema + arquivos referenciados existem + durações de áudio dentro de 30s–3min.
- Teste guiado por Playwright local: carregar app, tocar POI, player funciona, modo offline (bloquear rede) ainda renderiza.
- Teste real: abrir no iPhone do Wilton via URL do Pages, Add to Home Screen, ativar modo avião e conferir.

## Fora de escopo (v1)

Auto-play por proximidade; múltiplos idiomas; editor visual de roteiros; contas/telemetria; app nativo.

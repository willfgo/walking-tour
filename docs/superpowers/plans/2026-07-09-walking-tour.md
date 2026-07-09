# Walking Tour Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PWA de walking tour (mapa + fotos + narração) no GitHub Pages, com piloto Dubrovnik utilizável HOJE em modo flash (sem áudio) e áudios OmniVoice entrando progressivamente de madrugada.

**Architecture:** App estático genérico (`app/`) que renderiza qualquer cidade a partir de `cities/<slug>/tour.json`; service worker pré-cacheia app + mídia + tiles OSM da bbox do tour; pipeline local (`pipeline/`) gera fotos (Wikimedia) e áudio (OmniVoice MPS, sem fallback `say`).

**Tech Stack:** HTML/CSS/JS vanilla (sem build), Leaflet 1.9 vendorado, OSM tiles, Service Worker + Web App Manifest, Python 3 (pipeline), OmniVoice (venv py3.12, device mps), ffmpeg.

## Global Constraints

- Conteúdo em PT-BR; textos de narração 150–250 palavras (fala ~1–2 min).
- Voz: exclusivamente OmniVoice (ref `~/Desktop/Claude/omnivoice/ref-animada.wav`). **Nunca** usar `say` — áudio ausente = estado "áudio em preparo" no app.
- Fotos: apenas Wikimedia Commons com licença livre; crédito obrigatório (`credit`) exibido na legenda; **cada foto verificada visualmente** (Read da imagem) antes de entrar — nunca confiar só no nome do arquivo (regra do usuário).
- App 100% estático e self-contained: Leaflet vendorado (não CDN), sem framework, sem build step.
- Publicação: repo GitHub `willfgo/walking-tour` público, Pages servindo a raiz do branch `main`. Nunca force-push.
- Fase A (flash) tem prioridade absoluta — precisa estar no ar HOJE (09/07) antes de qualquer trabalho de áudio.
- Commits frequentes no worktree `dev`; publicar = push `dev:main`.

**Nota de execução (registrada):** o usuário está em viagem e autorizou execução direta ("propõe e já executa" / "pode seguir, me avise quando acabar"). Execução INLINE nesta sessão; subagents usados para pesquisa de conteúdo/fotos. Pela pressão de prazo, os passos de app trazem contratos e algoritmos exatos em vez de arquivos completos duplicados no plano — o código-fonte é a fonte da verdade, validado pelos passos de verificação de cada task.

---

## FASE A — modo flash (hoje)

### Task A1: Scaffold do app + mapa com rota e marcadores

**Files:**
- Create: `app/index.html`, `app/app.css`, `app/app.js`
- Create: `app/vendor/leaflet.js`, `app/vendor/leaflet.css`, `app/vendor/images/*` (baixados de unpkg leaflet@1.9.4)
- Create: `cities/dubrovnik/tour.json` (stub com 2 POIs de teste, coords reais)

**Interfaces (Produces):**
- `tour.json` schema conforme spec (`city, title, intro{text,audio}, route[[lat,lng]], pois[{id, order, name, lat, lng, duration_s, script, audio|null, photos[{file,caption,credit}], practical, maps_url}]`).
- `app.js`: `loadTour(citySlug) -> fetch cities/<slug>/tour.json`; cidade via `?city=` com fallback localStorage `wt-city`, default `dubrovnik`.
- Funções globais usadas pelas tasks seguintes: `openPoi(poiId)` (abre painel), `haversineM(a, b) -> metros`.

- [x] **Step 1:** Baixar Leaflet 1.9.4 (`curl -L https://unpkg.com/leaflet@1.9.4/dist/...` → `app/vendor/`), incluindo `images/` (marker-icon, marker-shadow).
- [x] **Step 2:** `index.html`: viewport mobile, `<div id="map">`, header com título da cidade + toggle mapa/lista, container do bottom sheet vazio. Carrega vendor + app.js com `defer`.
- [x] **Step 3:** `app.js`: init Leaflet (tiles `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, attribution OSM), fetch do tour.json, polyline da `route`, marcadores numerados (divIcon com número da ordem; verde quando visitado), `fitBounds` nos POIs. Erro de fetch/JSON → `<div class="error">` com mensagem legível.
- [x] **Step 4 (verify):** `python3 -m http.server 8777` na raiz do worktree + Playwright: abrir `http://localhost:8777/app/?city=dubrovnik`, screenshot mostra mapa com 2 marcadores numerados e rota. Console sem erros.
- [x] **Step 5:** Commit `feat: mapa base com rota e marcadores`.

### Task A2: Painel do POI (bottom sheet) + player com estado "áudio em preparo"

**Files:**
- Modify: `app/index.html`, `app/app.css`, `app/app.js`

**Interfaces:**
- Consumes: `openPoi(poiId)` ligado ao click do marker (A1).
- Produces: bottom sheet com: carrossel de fotos (scroll-snap horizontal, legenda+crédito), nome/ordem, player `<audio>` (quando `audio != null`) com play/pause, barra de progresso, velocidade 1×/1.25×/1.5×; quando `audio == null` → badge "🎙️ áudio em preparo" + script visível; transcrição colapsável (`<details>`) quando há áudio; bloco "info prática"; botão "Abrir no Maps" (`maps_url`); botão "✓ Visitado" (toggle, localStorage `wt-<city>-visited` array de ids, reflete no marker).

- [x] **Step 1:** Markup + CSS do sheet (fixo embaixo, ~65vh, fechar via botão ✕; dark-friendly; touch targets ≥44px).
- [x] **Step 2:** JS: render do sheet a partir do objeto POI; player com `playbackRate`; Media Session API (`title` = nome do POI, `artist` = "Walking Tour — <cidade>"); Wake Lock API request no primeiro play (re-request em `visibilitychange`).
- [x] **Step 3 (verify):** Playwright: click no marker 1 → sheet abre com foto e badge "áudio em preparo" (stub sem áudio); click "Visitado" → marker fica verde e persiste após reload.
- [x] **Step 4:** Commit `feat: painel de POI com fotos, player e visitado`.

### Task A3: Modo lista + distâncias a pé

**Files:**
- Modify: `app/app.js`, `app/app.css`, `app/index.html`

**Interfaces:**
- Consumes: `haversineM` (A1), `openPoi` (A2).
- Produces: view lista (ordem da caminhada): número, nome, 1ª foto em thumb, distância+minutos a pé até o PRÓXIMO ponto (`round(m)` e `ceil(m / 75)` min ≈ 4,5 km/h), check visitado. GPS: botão "📍" liga `navigator.geolocation.watchPosition` → ponto azul no mapa (circleMarker) + accuracy circle; erro/negado → toast discreto, app segue.

- [x] **Step 1:** Toggle mapa/lista no header (estado em localStorage `wt-view`).
- [x] **Step 2:** Render da lista + distâncias; click abre `openPoi`.
- [x] **Step 3:** Geolocalização com tratamento de erro (denied → toast "GPS indisponível — use o mapa").
- [x] **Step 4 (verify):** Playwright: alternar para lista, ver distâncias plausíveis entre os 2 POIs stub (Pile→Onofrio ≈ 100–200 m); console limpo.
- [x] **Step 5:** Commit `feat: modo lista com distâncias e GPS opcional`.

### Task A4: PWA — manifest + service worker + tiles offline

**Files:**
- Create: `app/manifest.webmanifest`, `app/sw.js`, `app/icon-192.png`, `app/icon-512.png`
- Create: `pipeline/gerar_precache.py`, `cities/dubrovnik/precache.json`
- Test: `pipeline/test_gerar_precache.py`

**Interfaces:**
- Produces: `gerar_precache.py <city>` lê `tour.json`, emite `precache.json`: `{"assets": [urls relativos de fotos/áudios existentes + tour.json], "tiles": ["https://tile.openstreetmap.org/z/x/y.png", ...]}` para bbox dos POIs + margem 120 m, zooms 15–17. Fórmula slippy-map: `x = floor((lon+180)/360 * 2^z)`; `y = floor((1 - asinh(tan(lat_rad))/π)/2 * 2^z)`.
- `sw.js`: precache no `install` (app shell hardcoded + fetch de `precache.json` de cada cidade listada em `app/cities.json`); estratégia: cache-first para tiles/fotos/áudio; stale-while-revalidate para tour.json/app shell. Versão do cache = string em `sw.js` (bump manual a cada publicação de conteúdo).

- [x] **Step 1 (TDD):** `test_gerar_precache.py`: (a) tile x/y correto para lat 42.6414, lng 18.1064 em z16 (comparar com fórmula de referência no teste); (b) bbox com margem inclui tiles vizinhos; (c) contagem de tiles z15–17 da Cidade Velha < 400. Rodar: FAIL (módulo não existe).
- [x] **Step 2:** Implementar `gerar_precache.py`; rodar `python3 -m pytest pipeline/ -q`: PASS.
- [x] **Step 3:** Ícones 192/512 px (fundo sólido + "WT", via ffmpeg lavfi/drawtext ou sips). Manifest: `display: standalone`, `start_url` relativo correto no Pages.
- [x] **Step 4:** `sw.js` + registro no app.js; `app/cities.json` = `["dubrovnik"]`.
- [x] **Step 5 (verify):** Playwright: 1º load com rede → 2º load com `context.setOffline(true)` → app renderiza mapa (tiles do cache) e abre POI.
- [x] **Step 6:** Commit `feat: PWA offline (manifest, service worker, precache de tiles)`.

### Task A5: Conteúdo Dubrovnik — roteiro, textos e info prática

**Files:**
- Modify: `cities/dubrovnik/tour.json` (substitui stub pelos ~11 POIs finais)

**Interfaces:**
- Produces: tour.json completo e validável; `route` = polyline seguindo a caminhada (pontos a cada ~30–80 m em ruas reais); todos os `audio: null` nesta fase.

- [x] **Step 1:** Subagents de pesquisa (paralelos): (a) fatos históricos + 1 curiosidade por POI com fontes; (b) coordenadas precisas de cada POI + info prática 2026 (preços/horários de Muralhas, Lovrijenac, Palácio do Reitor, Farmácia do Mosteiro). POIs: Pile Gate, Fonte Grande de Onofrio, Mosteiro Franciscano/Farmácia, Stradun, Palácio Sponza, Igreja de São Brás, Palácio do Reitor, Catedral, Praça Gundulić, Buža/muralhas sul, Forte Lovrijenac.
- [x] **Step 2:** Escrever os 11 scripts PT-BR (150–250 palavras; estrutura: gancho → história → curiosidade → "o que olhar agora"; UMA FRASE POR LINHA — requisito do pipeline de áudio) + intro de ~30 s. Escrever `practical` de cada POI.
- [x] **Step 3:** Montar `route` (traçado Pile→…→Lovrijenac) e `maps_url` por POI.
- [x] **Step 4 (verify):** JSON válido (`python3 -m json.tool`); contagem de palavras de cada script dentro de 150–250; coords dentro da bbox de Dubrovnik (42.63–42.65 / 18.10–18.12).
- [x] **Step 5:** Commit `feat: tour de Dubrovnik (11 POIs, textos e rota)`.

### Task A6: Fotos Wikimedia Commons

**Files:**
- Create: `pipeline/baixar_fotos.py`, `cities/dubrovnik/photos/*.jpg`
- Modify: `cities/dubrovnik/tour.json` (photos[])

**Interfaces:**
- Produces: `baixar_fotos.py` consulta a API do Commons (`action=query&generator=search&gsrsearch=<termo>&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=1600`), filtra licenças livres (CC-BY, CC-BY-SA, PD), baixa e salva `NN-slug-K.jpg`, emitindo `photos-manifest.json` com caption/credit/licença por arquivo para curadoria.
- 2–3 fotos por POI: 1 visão geral + 1 detalhe quando possível.

- [x] **Step 1:** Implementar e rodar `baixar_fotos.py` para os 11 POIs (termos de busca por POI num dicionário no script).
- [x] **Step 2 (curadoria obrigatória):** Read de CADA imagem baixada — conferir que mostra o POI certo e tem qualidade; descartar erradas/ruins e rebuscar. Redimensionar finais para ≤1280px (`sips -Z 1280`).
- [x] **Step 3:** Preencher `photos[]` no tour.json (caption PT-BR + credit da licença).
- [x] **Step 4 (verify):** todo POI com ≥1 foto; todos os arquivos referenciados existem; peso total `photos/` < 15 MB.
- [x] **Step 5:** Commit `feat: fotos dos POIs (Wikimedia Commons, com créditos)`.

### Task A7: Validador do tour

**Files:**
- Create: `pipeline/validar_tour.py`
- Test: `pipeline/test_validar_tour.py`

**Interfaces:**
- Produces: `validar_tour.py <city>` → exit 0/1 com relatório: campos obrigatórios, ids únicos, order contíguo desde 1, arquivos de foto/áudio existem, `duration_s` (quando audio≠null) entre 30 e 180 s medido via ffprobe (tolerância ±5 s), scripts 100–300 palavras, coords numéricas.

- [x] **Step 1 (TDD):** testes com tour mínimo válido e casos inválidos (foto faltando, order duplicado, script curto). FAIL.
- [x] **Step 2:** Implementar; `python3 -m pytest pipeline/ -q`: PASS.
- [x] **Step 3:** Rodar no dubrovnik real: PASS. Corrigir o que apontar.
- [x] **Step 4:** Commit `feat: validador de tour + verde no dubrovnik`.

### Task A8: Publicar no GitHub Pages + smoke test final

**Files:**
- Create: `README.md` (o que é, como usar no iPhone, como adicionar cidade)
- Create: `index.html` na raiz (redirect → `app/index.html`)

- [x] **Step 1:** Regenerar `precache.json` (fotos novas), bump versão do SW.
- [x] **Step 2:** Criar repo e publicar: `gh repo create willfgo/walking-tour --public` + remote + `git push -u origin dev:main` (a partir do worktree `dev`).
- [x] **Step 3:** Ativar Pages: `gh api repos/willfgo/walking-tour/pages -X POST -f "source[branch]=main" -f "source[path]=/"` (PUT se já existir). Aguardar `status: built` com loop `until` (sem `timeout` neste macOS).
- [x] **Step 4 (verify):** `curl -sI https://willfgo.github.io/walking-tour/app/` → 200; Playwright contra a URL pública: mapa, POI, foto, lista; offline após 1º load.
- [x] **Step 5:** Avisar o usuário (mensagem + PushNotification): URL, instrução "abrir no Safari → Compartilhar → Adicionar à Tela de Início; abrir 1× no wifi antes de sair".

## FASE B — áudio OmniVoice (madrugada)

### Task B1: Reconstruir o venv do OmniVoice

**Files:**
- Create: `~/Desktop/Claude/omnivoice/venv/` (fora do repo)

- [x] **Step 1:** `cd ~/Desktop/Claude/omnivoice && /opt/homebrew/opt/python@3.12/bin/python3.12 -m venv venv && venv/bin/pip install omnivoice` (cache pip de 1 GB + modelo HF de 3 GB já locais; wifi de hotel cobre só diffs).
- [x] **Step 2 (smoke):** sintetizar 1 frase teste com `--device mps --language pt` e o `ref-animada.wav`; conferir wav gerado e duração plausível (ffprobe). Se MPS falhar → diagnosticar com `--device cpu`, mas NÃO usar cpu para a fila (lento demais).
- [x] **Step 3:** Registrar tempo/frase medido para estimar a fila.

### Task B2: Pipeline de áudio (sem fallback say)

**Files:**
- Create: `pipeline/gerar_audio.py`
- Test: `pipeline/test_gerar_audio.py`

**Interfaces:**
- Consumes: scripts do tour.json (uma frase por linha, A5); OmniVoice CLI (B1).
- Produces: `gerar_audio.py <city> [--poi id]`: para cada POI com `audio: null` (ordem da caminhada, intro primeiro): sintetiza por frase (timeout 180 s, SEM fallback; frase que falhar → retry 1×; falhou de novo → aborta o POI, loga e segue), normaliza (24 kHz mono pcm_s16le), concat com silêncio 0,6 s, codifica `ffmpeg -c:a libmp3lame -q:a 5 -ac 1` → `audio/NN-slug.mp3`, mede duração (ffprobe), grava `audio` e `duration_s` no tour.json, regenera precache.json, bump SW version, `git add/commit/push dev:main` (publicação progressiva). Segmentos temporários em `$CLAUDE_JOB_DIR/tmp/audio-work/`.

- [x] **Step 1 (TDD):** testes das partes puras com runner fake (padrão do voz.py): divisão de frases ignora vazias/#; POI com falha não escreve `audio`; nome do mp3 = `NN-slug.mp3`. FAIL→PASS.
- [x] **Step 2:** Implementar (reusar padrões de `~/.claude/scripts/podcast-matinal/voz.py`, MENOS o fallback say).
- [x] **Step 3 (smoke):** gerar só a intro (~30 s) de ponta a ponta; validar mp3 no ffprobe e tocar no app local.
- [x] **Step 4:** Commit `feat: pipeline de áudio OmniVoice`.

### Task B3: Fila noturna + publicação progressiva

- [x] **Step 1:** Rodar `gerar_audio.py dubrovnik` em background (`run_in_background`), acompanhar via task-notification.
- [x] **Step 2:** Ao terminar: `validar_tour.py dubrovnik` (durações reais 30–180 s), Playwright no Pages (player funciona), avisar usuário (PushNotification: "áudios no ar — recarregue no wifi").

## FASE C — Zagreb (após B, antes de 12/07)

### Task C1: Conteúdo + fotos + áudio de Zagreb

- [x] **Step 1:** Repetir A5–A7 para `cities/zagreb/` (~6–8 POIs do centro: Trg bana Jelačića, Catedral, Dolac, Tkalčićeva, Porta de Pedra, São Marcos, Lotrščak/funicular, Teatro Nacional). Ajustar `app/cities.json`.
- [x] **Step 2:** `gerar_audio.py zagreb` + publicar. Avisar usuário.
- [x] **Step 3:** Seletor de cidade no app (visível quando `cities.json` tem >1 cidade).

## Verificação final (Definition of Done)

- [x] `pytest pipeline/ -q` verde.
- [x] `validar_tour.py` verde para dubrovnik (e zagreb na Fase C).
- [x] Pages no ar; smoke Playwright na URL pública (mapa, POI, foto, player ou badge, lista, offline).
- [x] Usuário avisado com URL + instruções de instalação e recarga de áudios.

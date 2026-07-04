# Editor de Vídeo — Clone IA

Interface web hospedada no Cloudflare em **natanmadeira.com.br/editor-video**.

Fluxo: cole um link do Instagram → o Worker resolve e baixa o vídeo → o
navegador corta em pedaços de 10s (ffmpeg.wasm) → cada pedaço é descrito pelo
Gemini e recriado com o seu clone pelo Veo (o modelo do Flow) → os clipes são
juntados no vídeo final, direto no navegador.

## Arquitetura

- **`worker.js`** — Cloudflare Worker. Serve os assets estáticos e expõe:
  - `GET /editor-video/api/resolve?url=` — extrai a URL do .mp4 de um post
    público do Instagram (via página de embed);
  - `GET /editor-video/api/fetch?url=` — proxy do download do CDN do
    Instagram (que não envia CORS). Restrito aos hosts `cdninstagram.com`
    e `fbcdn.net`.
- **`public/editor-video/index.html`** — o app inteiro (uma página).
  Corte/junção rodam no navegador com ffmpeg.wasm; as chamadas ao
  Gemini/Veo saem direto do navegador com a chave configurada pelo usuário
  (salva no localStorage — nunca passa pelo Worker).
- **`public/editor-video/vendor/`** — ffmpeg.wasm auto-hospedado. O
  `ffmpeg-core.wasm` (32 MB) excede o limite de 25 MiB por asset do
  Cloudflare, então está dividido em `ffmpeg-core.wasm.part0/part1` e é
  remontado no navegador via Blob.

## Configuração no site

A seção **⚙️ Configuração** do próprio site guarda:
- chave da API do Gemini (criar em https://aistudio.google.com/apikey);
- foto do clone (referência de aparência para o Veo);
- duração dos pedaços e dos clipes gerados, resolução e modelos.

## Deploy

```bash
cd editor-video
npm install wrangler
CLOUDFLARE_API_TOKEN=... npx wrangler deploy
```

A rota `natanmadeira.com.br/editor-video*` está declarada no
`wrangler.toml` (o domínio precisa estar na conta do Cloudflare).

## Desenvolvimento e teste

```bash
npx wrangler dev --port 8787   # http://localhost:8787/editor-video/
node e2e.mjs                   # teste ponta a ponta headless (corte+junção)
```

O `e2e.mjs` sobe o navegador, envia um vídeo local, roda o pipeline no modo
"só cortar e juntar" (sem gastar créditos) e confere duração/resolução do
resultado.

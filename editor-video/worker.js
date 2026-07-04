/**
 * Worker do Editor de Vídeo (natanmadeira.com.br/editor-video).
 *
 * Serve a interface (assets estáticos em public/) e expõe dois endpoints:
 *   GET /editor-video/api/resolve?url=<link do Instagram>
 *       Descobre a URL direta do arquivo .mp4 de um post/reel público.
 *   GET /editor-video/api/fetch?url=<url do CDN do Instagram>
 *       Faz o proxy do download do vídeo (o CDN do Instagram não manda CORS,
 *       então o navegador não consegue baixar direto).
 *
 * Todo o processamento pesado (corte, junção, chamadas ao Gemini/Veo)
 * acontece no navegador — o Worker só resolve e proxeia o download.
 */

const BROWSER_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
  "Accept-Language": "en-US,en;q=0.9",
};

// hosts de mídia do Instagram/Facebook permitidos no proxy
const ALLOWED_MEDIA_HOSTS = /(^|\.)cdninstagram\.com$|(^|\.)fbcdn\.net$/;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

function extractShortcode(link) {
  const m = String(link).match(
    /instagram\.com\/(?:[^/]+\/)?(?:reels?|p|tv)\/([A-Za-z0-9_-]+)/
  );
  return m ? m[1] : null;
}

function unescapeJsonString(raw) {
  try {
    return JSON.parse(`"${raw}"`);
  } catch {
    return raw.replace(/\\u0026/g, "&").replace(/\\\//g, "/");
  }
}

function findVideoUrl(html) {
  // formato clássico dos dados embutidos: "video_url":"https:\/\/..."
  let m = html.match(/"video_url"\s*:\s*"((?:[^"\\]|\\.)+)"/);
  if (m) return unescapeJsonString(m[1]);
  // JSON-LD: "contentUrl": "https://..."
  m = html.match(/"contentUrl"\s*:\s*"((?:[^"\\]|\\.)+)"/);
  if (m) return unescapeJsonString(m[1]);
  // tag <video src="...">
  m = html.match(/<video[^>]+src="([^"]+)"/);
  if (m) return m[1].replace(/&amp;/g, "&");
  return null;
}

async function apiResolve(url) {
  const link = url.searchParams.get("url") || "";
  const shortcode = extractShortcode(link);
  if (!shortcode) {
    return json(
      { error: "Link do Instagram inválido. Use o link de um post ou reel." },
      400
    );
  }

  // a página de embed costuma expor a URL do vídeo em posts públicos
  const candidates = [
    `https://www.instagram.com/p/${shortcode}/embed/captioned/`,
    `https://www.instagram.com/reel/${shortcode}/embed/`,
  ];
  for (const candidate of candidates) {
    try {
      const res = await fetch(candidate, { headers: BROWSER_HEADERS });
      if (!res.ok) continue;
      const html = await res.text();
      const videoUrl = findVideoUrl(html);
      if (videoUrl) return json({ videoUrl, shortcode });
    } catch {
      // tenta o próximo candidato
    }
  }
  return json(
    {
      error:
        "Não consegui extrair o vídeo desse link (o post pode ser privado ou " +
        "o Instagram bloqueou o acesso). Baixe o vídeo manualmente e use a " +
        "opção de enviar arquivo.",
    },
    422
  );
}

async function apiFetch(url) {
  const target = url.searchParams.get("url") || "";
  let parsed;
  try {
    parsed = new URL(target);
  } catch {
    return json({ error: "URL inválida." }, 400);
  }
  if (parsed.protocol !== "https:" || !ALLOWED_MEDIA_HOSTS.test(parsed.hostname)) {
    return json({ error: "Host não permitido no proxy." }, 403);
  }
  const upstream = await fetch(parsed.toString(), { headers: BROWSER_HEADERS });
  if (!upstream.ok) {
    return json({ error: `CDN respondeu ${upstream.status}.` }, 502);
  }
  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") || "video/mp4",
      "Cache-Control": "no-store",
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/editor-video/api/resolve") return apiResolve(url);
    if (url.pathname === "/editor-video/api/fetch") return apiFetch(url);
    return env.ASSETS.fetch(request);
  },
};

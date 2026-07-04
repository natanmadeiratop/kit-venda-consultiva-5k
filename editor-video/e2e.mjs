import { chromium } from 'playwright';

const TEST_VIDEO = '/tmp/claude-0/-home-user-kit-venda-consultiva-5k/1726b3e1-df63-5eb5-a939-dd66c4dda262/scratchpad/testjob/original.mp4';

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
const page = await browser.newPage();
page.on('console', (m) => { if (m.type() === 'error') console.log('[console.error]', m.text()); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));

await page.goto('http://127.0.0.1:8787/editor-video/');
console.log('title:', await page.title());

// config: apenas duração do pedaço (modo teste não precisa de API key)
await page.evaluate(() => { document.getElementById('cfg-details').open = true; });
await page.fill('#cfg-chunk', '10');
await page.click('#btn-save');
console.log('cfg-msg:', await page.textContent('#cfg-msg'));

// entrada: arquivo local + modo "só cortar e juntar"
await page.setInputFiles('#in-file', TEST_VIDEO);
await page.check('#in-skip');
await page.click('#btn-run');

// acompanha o status até o final (ffmpeg.wasm é lento; até 8 min)
const deadline = Date.now() + 8 * 60 * 1000;
let last = '';
while (Date.now() < deadline) {
  const status = (await page.textContent('#status-line'))?.trim();
  if (status && status !== last) { console.log('status:', status); last = status; }
  const done = await page.isVisible('#final-card');
  if (done && status?.includes('Pronto')) break;
  if (status?.startsWith('Erro:')) { console.log('FALHOU'); process.exit(1); }
  await new Promise((r) => setTimeout(r, 2000));
}

const nChunks = await page.locator('.chunk').count();
console.log('pedaços:', nChunks);

// baixa o mp4 final de dentro da página e valida com o ffprobe do sistema
// (o Chromium do Playwright não decodifica H.264, então nada de <video>)
const b64 = await page.evaluate(async () => {
  const r = await fetch(document.getElementById('final-dl').href);
  const buf = new Uint8Array(await r.arrayBuffer());
  let s = '';
  for (let i = 0; i < buf.length; i += 0x8000)
    s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  return btoa(s);
});
const { writeFileSync } = await import('node:fs');
const { tmpdir } = await import('node:os');
const outPath = tmpdir() + '/e2e-final.mp4';
writeFileSync(outPath, Buffer.from(b64, 'base64'));
await browser.close();

const { execSync } = await import('node:child_process');
const probe = execSync(
  `ffprobe -v error -select_streams v:0 -show_entries stream=width,height:format=duration -of json "${outPath}"`
).toString();
const info = JSON.parse(probe);
const dur = parseFloat(info.format.duration);
console.log('duração final:', dur.toFixed(1), 's | resolução:',
  info.streams[0].width + 'x' + info.streams[0].height);
const ok = nChunks === 3 && Math.abs(dur - 25) < 1.5;
console.log(ok ? 'E2E OK' : 'E2E INESPERADO');
process.exit(ok ? 0 : 1);

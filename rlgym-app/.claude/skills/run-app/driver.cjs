// One-shot driver for the RLGym GUI Electron app (dev mode).
// Launches Electron (+ the backend it spawns), runs the given steps, prints every log layer, quits.
//
//   node driver.cjs [step ...]
//
// Steps (run in order, after the home page has loaded and the backend status has resolved):
//   ss:<name>           screenshot -> $RLGYM_SHOT_DIR/<name>.png
//   goto:<hash-route>   navigate, e.g. goto:#/settings
//   click:<css>         DOM click on the first match
//   click-text:<text>   click the first button/link whose text contains <text>
//   type:<css>=<text>   fill an input
//   wait:<css>          wait up to 10 s for a selector
//   text[:<css>]        print innerText (whole body by default)
//   eval:<js>           evaluate in the renderer, print JSON
//   sleep:<ms>          pause
//   dark | light        emulate prefers-color-scheme
//   size:<w>x<h>        resize the window
// With no steps, it takes a single screenshot named "home".
//
// RLGYM_NG_PORT=<port> runs a private copy for parallel runs (e.g. one per git worktree): it always
// starts its own `ng serve` on that port (fails if the port is taken, never reuses another one), and
// uses its own Electron profile and screenshot dir. Without it: port 4200, reusing a running server.
const { _electron: electron } = require('playwright-core');
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO = path.resolve(__dirname, '../../../..');
const ELECTRON_DIR = path.join(REPO, 'electron');
const APP_DIR = path.join(REPO, 'rlgym-app');
const PRIVATE_PORT = process.env.RLGYM_NG_PORT;
const PORT = PRIVATE_PORT || '4200';
const DEV_URL = `http://localhost:${PORT}`;
const SUFFIX = PRIVATE_PORT ? `-${PORT}` : '';
const SHOT_DIR = process.env.RLGYM_SHOT_DIR || path.join(os.tmpdir(), 'rlgym-run' + SUFFIX);
const PROFILE_DIR = path.join(os.tmpdir(), 'rlgym-run-profile' + SUFFIX);
fs.mkdirSync(SHOT_DIR, { recursive: true });

const t0 = Date.now();
const log = (...a) => console.log(`+${String(Date.now() - t0).padStart(6)}ms`, ...a);
const lines = (tag) => (d) => String(d).split(/\r?\n/).filter(Boolean).forEach((l) => log(tag, l));

async function devServerUp() {
  try { return (await fetch(DEV_URL)).ok; } catch { return false; }
}

// Reuse a running `ng serve` (unless the port is private: it may be serving another worktree);
// otherwise start one and stop it at the end.
async function ensureDevServer() {
  if (await devServerUp()) {
    if (PRIVATE_PORT) throw new Error(`port ${PORT} is already in use - pick another RLGYM_NG_PORT`);
    log(`[ng] reusing dev server on :${PORT}`);
    return null;
  }
  log(`[ng] starting ng serve on :${PORT}...`);
  const ng = spawn('npx', ['ng', 'serve', '--port', PORT], { cwd: APP_DIR, shell: true, windowsHide: true });
  ng.stdout.on('data', lines('[ng]'));
  ng.stderr.on('data', lines('[ng:err]'));
  for (let i = 0; i < 120; i++) {
    if (await devServerUp()) { log('[ng] ready'); return ng; }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`ng serve did not come up on :${PORT} within 60 s`);
}

function killTree(proc) {
  if (!proc) return;
  try {
    if (process.platform === 'win32') execSync(`taskkill /PID ${proc.pid} /T /F`, { stdio: 'ignore' });
    else process.kill(-proc.pid);
  } catch { /* already gone */ }
}

async function runStep(page, step) {
  const i = step.indexOf(':');
  const [cmd, arg] = i < 0 ? [step, ''] : [step.slice(0, i), step.slice(i + 1)];
  switch (cmd) {
    case 'ss': {
      const f = path.join(SHOT_DIR, `${arg || 'shot-' + Date.now()}.png`);
      await page.screenshot({ path: f });
      return log('screenshot:', f);
    }
    case 'goto':
      await page.evaluate((h) => { location.hash = h.replace(/^#/, ''); }, arg);
      await page.waitForTimeout(300);
      return log('url:', page.url());
    case 'click':
      return log('click', arg, '->', await page.evaluate((s) => {
        const el = document.querySelector(s); if (!el) return 'NOT_FOUND'; el.click(); return 'OK';
      }, arg));
    case 'click-text':
      return log('click-text', JSON.stringify(arg), '->', await page.evaluate((t) => {
        const els = [...document.querySelectorAll('button, a, [role="button"]')];
        const el = els.find((e) => e.textContent?.trim() === t) ?? els.find((e) => e.textContent?.includes(t));
        if (!el) return 'NOT_FOUND'; el.click(); return 'OK: ' + el.tagName;
      }, arg));
    case 'type': {
      const j = arg.indexOf('=');
      await page.fill(arg.slice(0, j), arg.slice(j + 1));
      return log('typed into', arg.slice(0, j));
    }
    case 'wait':
      return page.waitForSelector(arg, { timeout: 10_000 })
        .then(() => log('found:', arg), () => log('TIMEOUT waiting for', arg));
    case 'text':
      return log('text:\n' + await page.evaluate((s) => (s ? document.querySelector(s) : document.body)?.innerText ?? '(null)', arg || null));
    case 'eval':
      try { return log('eval ->', JSON.stringify(await page.evaluate(arg))); }
      catch (e) { return log('eval ERROR:', e.message); }
    case 'sleep':
      return page.waitForTimeout(Number(arg) || 1000);
    case 'dark':
    case 'light':
      await page.emulateMedia({ colorScheme: cmd });
      return log('color scheme:', cmd);
    case 'size': {
      const [w, h] = arg.split('x').map(Number);
      await page.setViewportSize({ width: w, height: h });
      return log('size:', w, 'x', h);
    }
    default:
      return log('UNKNOWN STEP:', step);
  }
}

(async () => {
  const steps = process.argv.slice(2);
  if (!steps.length) steps.push('ss:home');

  const ng = await ensureDevServer();
  let app;
  try {
    app = await electron.launch({
      executablePath: path.join(ELECTRON_DIR, 'node_modules/electron/dist', process.platform === 'win32' ? 'electron.exe' : 'electron'),
      // Own profile dir: the app holds a single-instance lock per userData dir, so without this the
      // launch dies immediately whenever the user has their own copy open.
      // A private port gets a private profile too, so parallel runs don't share configs and settings.
      args: [ELECTRON_DIR, '--user-data-dir=' + PROFILE_DIR],
      cwd: ELECTRON_DIR,
      // VS Code exports ELECTRON_RUN_AS_NODE=1 to child processes, which turns electron.exe into plain Node.
      env: {
        ...Object.fromEntries(Object.entries(process.env).filter(([k]) => k !== 'ELECTRON_RUN_AS_NODE')),
        RLGYM_DEV_URL: DEV_URL,
      },
      timeout: 60_000,
    });
    // Main-process output, including the "[backend] ..." lines index.js forwards from uvicorn.
    app.process().stdout.on('data', lines('[main]'));
    app.process().stderr.on('data', lines('[main:err]'));

    const page = await app.firstWindow();
    page.on('console', (m) => log(`[renderer:${m.type()}]`, m.text().split('\n')[0]));
    page.on('pageerror', (e) => log('[renderer:pageerror]', e.message));
    page.on('requestfailed', (r) => log('[renderer:reqfailed]', r.method(), r.url(), r.failure()?.errorText));
    page.on('response', (r) => { if (r.url().startsWith('http://127.0.0.1')) log('[api]', r.status(), r.request().method(), r.url()); });

    await page.waitForLoadState('domcontentloaded');
    await page.waitForFunction(() => /running|unavailable/.test(document.querySelector('[role=status]')?.textContent ?? ''), null, { timeout: 15_000 })
      .catch(() => log('WARNING: backend status line never resolved (not on the home page?)'));
    log('ready. url:', page.url(), '| status:', JSON.stringify((await page.locator('[role=status]').textContent().catch(() => ''))?.replace(/\s+/g, ' ').trim()));

    for (const s of steps) await runStep(page, s);
  } finally {
    if (app) { await app.close().catch(() => {}); log('app closed'); }
    if (ng) { killTree(ng); log('[ng] stopped'); }
  }
})().catch((e) => { log('DRIVER ERROR:', e.message); process.exit(1); });

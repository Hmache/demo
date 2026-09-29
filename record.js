#!/usr/bin/env node
// Plays a scenario in headless Chromium and records it.
// Usage: node record.js scenario.json OUT_DIR            record (reads OUT_DIR/durations.json if present)
//        node record.js scenario.json OUT_DIR --dry      fast run, no capture (checks every selector)
//        node record.js scenario.json OUT_DIR --explore=N  fast-run the first N steps, then save
//            OUT_DIR/explore.png and print the visible interactive elements with selectors
// Scenario: JSON (see scenario.py to convert a plain-text scenario). Targets can be visible text or selectors.
// Writes OUT_DIR/frames/*.jpg + OUT_DIR/frames.json (CDP screencast, exact timestamps) and OUT_DIR/timing.json
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const scenario = /\.(txt|md)$/i.test(process.argv[2])
  ? JSON.parse(require('child_process').execFileSync('python3', [path.join(__dirname, 'scenario.py'), process.argv[2]], { encoding: 'utf8' }))
  : JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const OUT = process.argv[3];
const EXP = process.argv.find((a) => a.startsWith('--explore'));
const EXPLORE_N = EXP ? parseInt(EXP.split('=')[1] ?? '0', 10) || 0 : null;
const DRY = process.argv.includes('--dry') || EXPLORE_N !== null;   // fast run, no capture
const durPath = path.join(OUT, 'durations.json');
const durations = fs.existsSync(durPath) ? JSON.parse(fs.readFileSync(durPath, 'utf8')) : {};
const VP = scenario.viewport || { width: 1920, height: 1080 };
const GAP = scenario.gapAfterVoice ?? 0.6;             // silence after each narration line (s)
const MIN_HOLD = scenario.minStepHold ?? 1.5;          // min on-screen time for silent steps (s)
const TYPE_DELAY = scenario.typeDelay ?? 55;           // ms per character
const sleep = (ms) => new Promise((r) => setTimeout(r, DRY ? Math.min(ms, 20) : ms));

// Fake cursor + click ripple, re-injected on every navigation.
const OVERLAY = `(() => {
  const install = () => {
    if (document.getElementById('__demo_cursor')) return;
    const st = document.createElement('style');
    st.textContent = \`#__demo_cursor{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;
      transform:translate(var(--x,-100px),var(--y,-100px));transition:transform 0s}
    #__demo_cursor svg{filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
    .__demo_ripple{position:fixed;z-index:2147483646;pointer-events:none;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;
      background:rgba(37,99,235,.35);border:2px solid rgba(37,99,235,.9);animation:__demo_r .55s ease-out forwards}
    @keyframes __demo_r{to{transform:scale(4.2);opacity:0}}
    .__demo_hl{position:fixed;z-index:2147483645;pointer-events:none;border:3px solid #2563eb;border-radius:8px;
      box-shadow:0 0 0 4px rgba(37,99,235,.25),0 0 0 9999px rgba(15,23,42,.28);opacity:0;transition:opacity .35s}
    .__demo_hl.on{opacity:1}
    body.__demo_zoom{transition:transform .7s cubic-bezier(.4,0,.2,1)!important}
    #__demo_cursor.touch{width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;background:rgba(37,99,235,.35);border:2px solid rgba(255,255,255,.9);box-shadow:0 2px 8px rgba(0,0,0,.3)}
    #__demo_cursor.touch svg{display:none}
    .__demo_key{position:fixed;right:28px;bottom:28px;z-index:2147483647;pointer-events:none;font:600 20px/1 Inter,system-ui,sans-serif;color:#fff;
      background:rgba(15,23,42,.88);border:1px solid rgba(255,255,255,.25);border-radius:10px;padding:12px 16px;box-shadow:0 4px 16px rgba(0,0,0,.35);
      opacity:0;transform:translateY(8px);transition:opacity .18s,transform .18s}
    .__demo_key.on{opacity:1;transform:none}
    .__demo_callout{position:fixed;z-index:2147483646;pointer-events:none;font:600 16px/1.2 Inter,system-ui,sans-serif;color:#fff;background:var(--demo-brand,#2563eb);
      padding:10px 14px;border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,.28);white-space:nowrap;opacity:0;transform:translate(-50%,6px);transition:opacity .25s,transform .25s}
    .__demo_callout:after{content:'';position:absolute;left:50%;bottom:-7px;margin-left:-7px;border:7px solid transparent;border-bottom:0;border-top-color:var(--demo-brand,#2563eb)}
    .__demo_callout.on{opacity:1;transform:translate(-50%,0)}\`;
    document.documentElement.appendChild(st);
    const c = document.createElement('div');
    c.id = '__demo_cursor'; if (window.__demoTouch) c.className = 'touch';
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 26 26"><path d="M3 2 L3 21 L8.2 16.3 L11.6 24 L15 22.5 L11.7 14.9 L18.8 14.9 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(c);
    const p = window.__demoPos; if (p) { c.style.setProperty('--x', p.x + 'px'); c.style.setProperty('--y', p.y + 'px'); }
  };
  document.addEventListener('mousemove', (e) => {
    window.__demoPos = { x: e.clientX, y: e.clientY };
    const c = document.getElementById('__demo_cursor'); if (!c) return;
    c.style.setProperty('--x', e.clientX + 'px'); c.style.setProperty('--y', e.clientY + 'px');
  }, true);
  document.addEventListener('mousedown', (e) => {
    const r = document.createElement('div'); r.className = '__demo_ripple';
    r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
    document.documentElement.appendChild(r); setTimeout(() => r.remove(), 700);
  }, true);
  window.__demoKey = (label) => {
    let k = document.getElementById('__demo_key');
    if (!k) { k = document.createElement('div'); k.id = '__demo_key'; k.className = '__demo_key'; document.documentElement.appendChild(k); }
    k.textContent = label; k.classList.add('on');
    clearTimeout(window.__demoKeyT); window.__demoKeyT = setTimeout(() => k.classList.remove('on'), 900);
  };
  window.__demoCallout = (text, r) => {          // r = element box, or null to clear
    let c = document.getElementById('__demo_co');
    if (!r) { if (c) { c.classList.remove('on'); setTimeout(() => c.remove(), 300); } return; }
    if (!c) { c = document.createElement('div'); c.id = '__demo_co'; c.className = '__demo_callout'; document.documentElement.appendChild(c); }
    c.textContent = text;
    c.style.left = (r.x + r.width / 2) + 'px';
    c.style.top = 'auto'; c.style.bottom = (window.innerHeight - r.y + 12) + 'px';
    requestAnimationFrame(() => c.classList.add('on'));
  };
  window.__demoHighlight = (r) => {            // r = {x,y,width,height} or null to clear
    let h = document.getElementById('__demo_hl');
    if (!r) { if (h) { h.classList.remove('on'); setTimeout(() => h.remove(), 400); } return; }
    if (!h) { h = document.createElement('div'); h.id = '__demo_hl'; h.className = '__demo_hl'; document.documentElement.appendChild(h); }
    const pad = 6;
    Object.assign(h.style, { left: (r.x - pad) + 'px', top: (r.y - pad) + 'px', width: (r.width + 2 * pad) + 'px', height: (r.height + 2 * pad) + 'px' });
    requestAnimationFrame(() => h.classList.add('on'));
  };
  window.__demoZoom = (k, cx, cy) => {           // k = 1 resets; cx,cy = viewport point that ends up centered
    const b = document.body; b.classList.add('__demo_zoom');
    if (k === 1) { b.style.transform = ''; b.style.transformOrigin = ''; return; }
    const W = document.documentElement.clientWidth, H = document.documentElement.clientHeight;
    const pw = Math.max(W, b.scrollWidth), ph = Math.max(H, b.scrollHeight);
    const px = cx, py = cy + window.scrollY;          // origin in body coordinates
    // translate so the point lands in the middle, clamped so no blank area appears
    let dx = W / 2 - cx, dy = H / 2 - cy;
    dx = Math.min(dx, (k - 1) * px); dx = Math.max(dx, W - px - (pw - px) * k);
    dy = Math.min(dy, (k - 1) * py); dy = Math.max(dy, H - py - (ph - py) * k);
    b.style.transformOrigin = px + 'px ' + py + 'px';
    b.style.transform = 'translate(' + dx + 'px,' + dy + 'px) scale(' + k + ')';
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
})();`;

(async () => {
  const DSF = scenario.scale ?? 1;                       // 2 = retina-sharp video (output = viewport x 2)
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || undefined,
    args: DSF !== 1 ? [`--force-device-scale-factor=${DSF}`] : [] });
  const ctxOpts = { viewport: VP, deviceScaleFactor: DSF, locale: scenario.locale || 'en-US' };
  if (scenario.mobile) Object.assign(ctxOpts, { isMobile: true, hasTouch: true,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
  if (scenario.storageState) ctxOpts.storageState = scenario.storageState;
  if (scenario.httpCredentials) ctxOpts.httpCredentials = scenario.httpCredentials;
  const ctx = await browser.newContext(ctxOpts);
  await ctx.addInitScript(`window.__demoTouch = ${!!scenario.mobile}; document.documentElement.style.setProperty('--demo-brand', ${JSON.stringify(scenario.brandColor || '#2563eb')});`);
  await ctx.addInitScript(OVERLAY);
  const page = await ctx.newPage();
  // High-quality capture: CDP screencast gives JPEG frames with wall-clock timestamps,
  // so frames and step times share one clock (perfect voice sync, no encoder blur).
  const frames = [];
  const FR = path.join(OUT, 'frames');
  const cdp = await ctx.newCDPSession(page);
  if (!DRY) {
    fs.rmSync(FR, { recursive: true, force: true });
    fs.mkdirSync(FR, { recursive: true });
    cdp.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
      const f = `f${String(frames.length).padStart(6, '0')}.jpg`;
      fs.writeFileSync(path.join(FR, f), Buffer.from(data, 'base64'));
      frames.push({ f, t: metadata.timestamp * 1000 });
      cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
    });
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: scenario.jpegQuality ?? 92,
      maxWidth: VP.width * DSF, maxHeight: VP.height * DSF, everyNthFrame: 1 });
  }
  const t0 = Date.now();
  const now = () => (Date.now() - t0) / 1000;
  let pos = { x: VP.width / 2, y: VP.height / 2 };

  // Cookie banners: click a "decline / only necessary" button if there is one, otherwise hide the banner.
  const DECLINE = ['Reject all', 'Reject All', 'Decline', 'Decline all', 'Refuse', 'Deny', 'Only necessary', 'Necessary only',
    'Continue without accepting', 'Tout refuser', 'Refuser', 'Refuser tout', 'Continuer sans accepter', 'Alle ablehnen', 'Rechazar todo'];
  const dismissCookies = async () => {
    for (const label of DECLINE) {
      const b = page.getByRole('button', { name: label }).first();
      if (await b.isVisible().catch(() => false)) { await b.click({ timeout: 2000 }).catch(() => {}); await sleep(400); return 'clicked ' + label; }
    }
    const hidden = await page.evaluate(() => {
      const sel = '[id*="cookie" i],[class*="cookie" i],[id*="consent" i],[class*="consent" i],[aria-label*="cookie" i],#onetrust-consent-sdk,#CybotCookiebotDialog,.cc-window,#didomi-host,#axeptio_overlay';
      let n = 0;
      document.querySelectorAll(sel).forEach((e) => { const r = e.getBoundingClientRect();
        if (r.width * r.height > 20000 && getComputedStyle(e).position !== 'static') { e.style.setProperty('display', 'none', 'important'); n++; } });
      document.body.style.overflow = ''; return n;
    });
    return hidden ? 'hid ' + hidden : 'none';
  };

  const settle = async () => {
    await page.waitForLoadState('domcontentloaded');
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
    await page.evaluate(() => document.fonts && document.fonts.ready).catch(() => {});
    if (scenario.cookies === 'dismiss') await dismissCookies();
    await page.mouse.move(pos.x, pos.y);              // re-show cursor after navigation
  };

  // Eased, visible cursor travel (~350-800 ms depending on distance).
  const moveTo = async (x, y) => {
    const dist = Math.hypot(x - pos.x, y - pos.y);
    const n = Math.max(12, Math.min(40, Math.round(dist / 25)));
    for (let k = 1; k <= n; k++) {
      const t = k / n, e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      await page.mouse.move(pos.x + (x - pos.x) * e, pos.y + (y - pos.y) * e);
      await sleep(16);
    }
    pos = { x, y };
  };

  // A target is either a CSS/Playwright selector or plain visible text ("Sign in", "Search", "Completed").
  // Plain text is matched against buttons, links, tabs, placeholders, labels, then any text.
  // Add " #2" to pick the 2nd match; a bare role word ("checkbox #1", "button #3") picks by role.
  const ROLES = ['button', 'link', 'checkbox', 'radio', 'textbox', 'combobox', 'tab', 'menuitem', 'option', 'switch', 'heading', 'img', 'row'];
  const isSelector = (t) => /^(css=|xpath=|text=|role=|\/\/|[.#\[])/.test(t) || t.includes('>>') || /^[a-z][a-z0-9-]*[.#\[:]/.test(t);
  const resolve = async (raw, timeout = 15000) => {
    const m = raw.match(/^(.*?)\s+#(\d+)$/);
    const t = (m ? m[1] : raw).trim(), idx = m ? parseInt(m[2], 10) - 1 : 0;
    let cands;
    if (isSelector(t)) cands = [page.locator(t.replace(/^css=/, ''))];
    else if (ROLES.includes(t.toLowerCase())) cands = [page.getByRole(t.toLowerCase())];
    else cands = [
      ...['button', 'link', 'tab', 'menuitem', 'checkbox', 'radio', 'option', 'switch', 'combobox', 'textbox']
        .map((r) => page.getByRole(r, { name: t, exact: true })),
      page.getByPlaceholder(t, { exact: true }), page.getByLabel(t, { exact: true }), page.getByText(t, { exact: true }),
      ...['button', 'link', 'tab', 'menuitem'].map((r) => page.getByRole(r, { name: t })),
      page.getByPlaceholder(t), page.getByLabel(t), page.getByText(t),
    ];
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      for (const c of cands) {
        const l = c.nth(idx);
        if (await l.isVisible().catch(() => false)) return l;
      }
      await new Promise((r) => setTimeout(r, 250));
    }
    const seen = await page.evaluate(() => [...document.querySelectorAll('a,button,input,textarea,select,[role=button],[role=link],[role=tab],label,h1,h2,h3')]
      .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2; })
      .map((e) => (e.matches('input,textarea,select') ? (e.placeholder || e.getAttribute('aria-label') || e.name || '') : (e.innerText || e.getAttribute('aria-label') || '')).trim().replace(/\s+/g, ' ').slice(0, 40))
      .filter((x) => x)).catch(() => []);
    const grams = (x) => { x = x.toLowerCase(); const g = new Set(); for (let i = 0; i < x.length - 1; i++) g.add(x.slice(i, i + 2)); return g; };
    const gt = grams(t);
    const close = [...new Set(seen)].map((x) => { const gx = grams(x); let c = 0; gt.forEach((b) => { if (gx.has(b)) c++; });
      return [x, gt.size + gx.size ? (2 * c) / (gt.size + gx.size) : 0]; }).filter((p) => p[1] > 0.25).sort((a, b) => b[1] - a[1]).slice(0, 5).map((p) => `"${p[0]}"`);
    throw new Error(`could not find "${raw}" on ${page.url()}` + (close.length ? `. Did you mean ${close.join(', ')}?` : '') +
      ` (looked for a button, link, field placeholder/label or text; run with --explore to list the page)`);
  };

  const target = async (selector) => {
    const loc = await resolve(selector);
    await loc.scrollIntoViewIfNeeded();
    await sleep(250);
    const b = await loc.boundingBox();
    return { loc, x: b.x + b.width / 2, y: b.y + b.height / 2 };
  };

  const run = async (a) => {
    switch (a.type) {
      case 'goto': await page.goto(a.url); await settle(); break;
      case 'click': { const t = await target(a.selector); await moveTo(t.x, t.y); await sleep(150);
        if (scenario.highlightClicks) { const b = await t.loc.boundingBox(); await page.evaluate((r) => window.__demoHighlight(r), b); await sleep(500);
          await page.evaluate(() => window.__demoHighlight(null)); await sleep(150); }
        const u = page.url();
        await page.mouse.down(); await sleep(70); await page.mouse.up(); await sleep(350);
        if (a.navigates || page.url() !== u) await settle(); break; }
      case 'hover': { const t = await target(a.selector); await moveTo(t.x, t.y); await sleep(a.ms ?? 600); break; }
      case 'type': if (!a.selector) { await page.keyboard.type(a.text, { delay: DRY ? 0 : (a.delay ?? TYPE_DELAY) }); await sleep(250); break; }
      { const t = await target(a.selector); await moveTo(t.x, t.y);
        if (!(await t.loc.evaluate((el) => el === document.activeElement))) { await page.mouse.down(); await page.mouse.up(); }
        if (a.clear) await t.loc.fill('');
        await t.loc.pressSequentially(a.text, { delay: DRY ? 0 : (a.delay ?? TYPE_DELAY) }); await sleep(250); break; }
      case 'fill': { const t = await target(a.selector); await moveTo(t.x, t.y); await t.loc.fill(a.text); await sleep(300); break; }
      case 'select': { const t = await target(a.selector); await moveTo(t.x, t.y); await t.loc.selectOption(a.value); await sleep(400); break; }
      case 'press': { const u = page.url();
        if (scenario.showKeys !== false) { const label = a.key.split('+').map((k) => ({ Meta: '\u2318', Control: 'Ctrl', Alt: '\u2325', Shift: '\u21E7', Enter: '\u21B5 Enter', Escape: 'Esc', ArrowDown: '\u2193', ArrowUp: '\u2191', Tab: 'Tab \u21E5' }[k] || k)).join(' + ');
          await page.evaluate((l) => window.__demoKey(l), label); await sleep(250); }
        await page.keyboard.press(a.key); await sleep(350);
        if (a.navigates || page.url() !== u) await settle(); break; }
      case 'scroll': { // smooth wheel scroll by a.y px (or to a.selector)
        let dy = a.y ?? 600;
        if (a.selector) { const b = await (await resolve(a.selector)).boundingBox(); dy = b.y - (a.offset ?? 120); }
        const n = Math.max(10, Math.round(Math.abs(dy) / 40));
        for (let k = 0; k < n; k++) { await page.mouse.wheel(0, dy / n); await sleep(18); }
        await sleep(400); break; }
      case 'moveTo': await moveTo(a.x, a.y); break;
      case 'highlight': { const t = await target(a.selector); await moveTo(t.x, t.y); const b = await t.loc.boundingBox();
        await page.evaluate((r) => window.__demoHighlight(r), b); await sleep(a.ms ?? 1500);
        await page.evaluate(() => window.__demoHighlight(null)); await sleep(400); break; }
      case 'zoom': { // zoom {selector, factor?} zooms towards an element; zoom {factor: 1} resets
        const k = a.factor ?? 1.8;
        if (k === 1 || !a.selector) { await page.evaluate(() => window.__demoZoom(1)); await sleep(800); break; }
        const t = await target(a.selector); await moveTo(t.x, t.y);
        await page.evaluate(([k, x, y]) => window.__demoZoom(k, x, y), [k, t.x, t.y]); await sleep(750);
        const b2 = await t.loc.boundingBox(); if (b2) await moveTo(b2.x + b2.width / 2, b2.y + b2.height / 2);
        await sleep(a.ms ?? 600); break; }
      case 'dismissCookies': console.log('cookies: ' + await dismissCookies()); break;
      case 'callout': { const t = await target(a.selector); const b = await t.loc.boundingBox();
        await page.evaluate(([txt, r]) => window.__demoCallout(txt, r), [a.text, b]); await sleep(a.ms ?? 2000);
        await page.evaluate(() => window.__demoCallout(null, null)); await sleep(300); break; }
      case 'wait': await sleep(a.ms ?? 1000); break;
      case 'waitFor': if (a.state === 'hidden') await page.locator(a.selector).first().waitFor({ state: 'hidden', timeout: a.timeout ?? 20000 });
        else await resolve(a.selector, a.timeout ?? 20000); break;
      case 'waitForUrl': await page.waitForURL(a.url, { timeout: a.timeout ?? 20000 }); await settle(); break;
      case 'eval': await page.evaluate(a.js); await sleep(300); break;
      default: throw new Error('unknown action ' + a.type);
    }
  };

  const explore = async () => {
    await page.screenshot({ path: path.join(OUT, 'explore.png') });
    const els = await page.evaluate(() => {
      const q = 'a,button,input,textarea,select,[role=button],[role=link],[role=tab],[role=menuitem],[role=checkbox],[contenteditable=true],summary,label';
      const esc = (t) => t.replace(/'/g, "\\'");
      return [...document.querySelectorAll(q)].filter((e) => {
        const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
        return r.width > 2 && r.height > 2 && cs.visibility !== 'hidden' && cs.display !== 'none' && e.id !== '__demo_cursor';
      }).slice(0, 150).map((e) => {
        const tag = e.tagName.toLowerCase(), txt = (e.matches('input,textarea,select') ? '' : e.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 50);
        const lab = e.getAttribute('aria-label') || e.getAttribute('placeholder') || e.getAttribute('name') || '';
        let sel = e.id ? '#' + CSS.escape(e.id)
          : e.getAttribute('data-testid') ? `[data-testid="${e.getAttribute('data-testid')}"]`
          : lab ? `${tag}[${e.getAttribute('aria-label') ? 'aria-label' : e.getAttribute('placeholder') ? 'placeholder' : 'name'}="${lab}"]`
          : txt ? `${tag}:has-text('${esc(txt.slice(0, 30))}')` : tag + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/)[0] : '');
        const r = e.getBoundingClientRect();
        return [sel, `<${tag}${e.type ? ' type=' + e.type : ''}> text: "${txt || lab}" @${Math.round(r.x)},${Math.round(r.y)}`];
      }).map((x, _, all) => { const same = all.filter((y) => y[0] === x[0]);
        return (same.length > 1 ? `${x[0]} >> nth=${same.indexOf(x)}` : x[0]) + '   ' + x[1]; });
    });
    console.log(`URL: ${page.url()}\nTITLE: ${await page.title()}\n--- interactive elements ---\n` + els.join('\n'));
    console.log(`Screenshot: ${OUT}/explore.png`);
  };

  const timing = { steps: [] };
  let failed = null;
  try {
    await page.goto(scenario.url);
    await settle();
    await sleep(400);
    timing.trimStart = now();                          // cut the blank frames before first paint
    const N = EXPLORE_N !== null ? Math.min(EXPLORE_N, scenario.steps.length) : scenario.steps.length;
    for (let i = 0; i < N; i++) {
      const s = scenario.steps[i];
      const start = now();
      timing.steps.push({ i, start, say: s.say || '' });
      for (const a of s.actions || []) await run(a);
      const voice = durations[String(i)];
      const hold = voice != null ? voice + GAP : MIN_HOLD;
      const rest = hold - (now() - start);
      if (rest > 0) await sleep(rest * 1000);
      timing.steps[i].end = now();
      console.log(`step ${i} ${start.toFixed(2)}s -> ${timing.steps[i].end.toFixed(2)}s`);
    }
    if (EXPLORE_N !== null) await explore();
    await sleep((scenario.outroHold ?? 1.0) * 1000);
  } catch (e) {
    failed = e;
    await page.screenshot({ path: path.join(OUT, 'failure.png') }).catch(() => {});
  }
  timing.end = now();
  if (!DRY) await cdp.send('Page.stopScreencast').catch(() => {});
  await ctx.close();
  await browser.close();
  if (!DRY) {
    fs.writeFileSync(path.join(OUT, 'frames.json'), JSON.stringify(frames.map((x) => ({ f: x.f, t: (x.t - t0) / 1000 }))));
    fs.writeFileSync(path.join(OUT, 'timing.json'), JSON.stringify(timing, null, 1));
  }
  if (failed) {
    console.error(`FAILED at step ${timing.steps.length - 1}: ${failed.message}\nScreenshot: ${OUT}/failure.png`);
    process.exit(1);
  }
})();

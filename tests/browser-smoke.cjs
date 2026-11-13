// npm install --prefix .validation playwright@1.56.1
// PLAYWRIGHT_BROWSERS_PATH=.validation/browsers node tests/browser-smoke.cjs
// Serves the pinned, unmodified game assets. This is a boot test, not a login test.
const http = require('node:http');
const fs = require('node:fs');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('../.validation/node_modules/playwright');
const runtime = 'web/ruffle/node_modules/@ruffle-rs/ruffle';
const requests = [];
const errors = [];
const failures = [];
const mediaRef = execFileSync('git', ['-c', `safe.directory=${process.cwd().replaceAll('\\', '/')}`, 'rev-parse', 'HEAD:legacy-media'], { encoding: 'utf8' }).trim();
const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    requests.push(url.pathname);
    try {
        if (url.pathname === '/') {
            res.setHeader('Content-Type', 'text/html');
            res.end(`<!doctype html><html><head><script>window.RufflePlayer={config:{polyfills:false}}</script>
            <script defer src="/__wand/ruffle/ruffle.js"></script><script defer src="/__wand/ruffle/legacy.js"></script></head>
            <body><div id="wand-game" data-media="http://127.0.0.1:${server.address().port}/media" data-address="game.example.test" data-login-port="6112" data-language="en">
            <p id="wand-status">Loading</p></div><script>function grecaptchaSubmit(){document.getElementById('game').finishedCaptcha('houdini')}</script></body></html>`);
            return;
        }
        let file;
        if (url.pathname.startsWith('/__wand/ruffle/')) {
            const name = path.basename(url.pathname);
            file = fs.readFileSync(['legacy.js', 'legacy.css'].includes(name) ? `web/ruffle/${name}` : `${runtime}/${name}`);
        } else {
            let mediaPath = url.pathname.replace(/^\/media/, '');
            if (mediaPath === '/servers.xml') {
                file = Buffer.from(fs.readFileSync('servers.xml', 'utf8').replaceAll('{{ .Env.GAME_ADDRESS }}', 'game.example.test').replaceAll('{{ .Env.GAME_LOGIN_PORT }}', '6112'));
            } else {
                const root = /\/web_service\//.test(mediaPath) ? 'play' : 'media';
                file = execFileSync('git', ['-C', 'legacy-media', '-c', `safe.directory=${process.cwd().replaceAll('\\', '/')}/legacy-media`, 'show', `${mediaRef}:${root}${mediaPath}`], { maxBuffer: 20 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
            }
        }
        const ext = path.extname(url.pathname);
        res.setHeader('Content-Type', ({ '.wasm': 'application/wasm', '.js': 'text/javascript', '.swf': 'application/x-shockwave-flash', '.xml': 'text/xml' })[ext] || 'application/octet-stream');
        res.end(file);
    } catch (error) {
        failures.push(url.pathname);
        res.writeHead(404).end();
    }
});
(async () => {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    let browser;
    try {
        browser = await chromium.launch({ headless: true, args: ['--enable-unsafe-swiftshader'] });
        const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
        page.on('pageerror', error => errors.push(error.message));
        page.on('requestfailed', request => errors.push(`${request.url()}: ${request.failure().errorText}`));
        page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
        await page.goto(`http://127.0.0.1:${server.address().port}/`);
        await page.waitForFunction(() => document.querySelector('#game') && document.querySelector('#wand-status').hidden, { timeout: 30000 });
        // Wait for the bootstrap, shell and server list rather than assuming load() means game ready.
        const deadline = Date.now() + 30000;
        while (!requests.includes('/media/servers.xml') && Date.now() < deadline) await page.waitForTimeout(250);
        await page.waitForTimeout(3000);
        fs.mkdirSync('.validation', { recursive: true });
        await page.screenshot({ path: '.validation/ruffle-boot.png' });
        const report = { requests, failures, errors };
        fs.writeFileSync('.validation/browser-report.json', JSON.stringify(report, null, 2));
        console.log(JSON.stringify(report, null, 2));
        assert(requests.includes('/media/boots.swf'));
        assert(requests.includes('/media/play/v2/client/load.swf'));
        assert(requests.includes('/media/play/v2/client/shell.swf'));
        assert(requests.includes('/media/servers.xml'));
        assert.equal(failures.length, 0, 'all requested game assets must be available');
        assert.equal(errors.length, 0, 'boot must have no browser errors or warnings');
    } finally {
        if (browser) await browser.close();
        server.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });

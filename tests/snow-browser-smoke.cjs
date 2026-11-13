// npm install --prefix .validation playwright@1.56.1
// PLAYWRIGHT_BROWSERS_PATH=.validation/browsers node tests/snow-browser-smoke.cjs
// Real Snow SWF -> Ruffle -> fixture WebSocket; no real accounts, server or login.
// Checks the place_context wire format accepted by Snowflake, not a complete game.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('../.validation/node_modules/playwright');
const runtime = 'web/ruffle/node_modules/@ruffle-rs/ruffle';
// Fixture WebSocket server bundled with the pinned Playwright.
const { wsServer } = require('../.validation/node_modules/playwright-core/lib/utilsBundle.js');
const requests = [];
const errors = [];
const packets = [];
let probingSnow = false;
const failures = [];
const env = { WEB_VANILLA_PLAY: '', WEB_VANILLA_MEDIA: '', GAME_ADDRESS: 'game.example.test', GAME_LOGIN_PORT: '6112', WEB_RECAPTCHA_SITE: '',
    SNOWFLAKE_HOST: 'snow.example.test', SNOWFLAKE_PORT: '7002' };
function render(text) {
    return text.replace(/{{ if \.Env.WEB_RECAPTCHA_SITE }}[\s\S]*?{{ end }}/g, '')
        .replace(/{{ if ne \.Env.VANILLA_PLAYER "flash" }}|{{ end }}/g, '')
        .replace(/{{ \(parseUrl \.Env.WEB_VANILLA_PLAY\).Host }}/g, new URL(env.WEB_VANILLA_PLAY).host)
        .replace(/{{ \.Env\.(\w+)(?: \| html)? }}/g, (_, key) => env[key] || '');
}
const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    requests.push(url.pathname);
    try {
        let file;
        if (url.pathname.endsWith('/web-service/snfgenerator/session')) {
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ hasError: false, error: '', data: 'probe' }));
            return;
        }
        if (url.pathname.includes('start_world_request')) {
            res.end('[S_WORLDLIST]|probe|cjsnow_0|snow.example.test|7002||crowdcontrol|cjsnow_0|CPNext_dev_branch|example');
            return;
        }
        if (url.pathname === '/datatech/serverlog/v1/json') { res.writeHead(204).end(); return; }
        if (url.pathname === '/') {
            res.setHeader('Content-Type', 'text/html');
            res.end(render(fs.readFileSync('templates/vanilla-media/play/index.html.template', 'utf8')));
            return;
        } else if (url.pathname.startsWith('/__wand/ruffle/')) {
            const name = path.basename(url.pathname);
            file = fs.readFileSync(name === 'vanilla.js' ? `web/ruffle/${name}` : `${runtime}/${name}`);
        } else if (url.pathname === '/media/play/web_service/environment_data.xml') {
            file = Buffer.from(render(fs.readFileSync('templates/vanilla-media/media/play/web_service/environment_data.xml.template', 'utf8')));
        } else if (url.pathname === '/servers.xml') {
            file = Buffer.from(fs.readFileSync('servers.xml', 'utf8').replaceAll('{{ .Env.GAME_ADDRESS }}', env.GAME_ADDRESS).replaceAll('{{ .Env.GAME_LOGIN_PORT }}', env.GAME_LOGIN_PORT));
        } else {
            const root = url.pathname.startsWith('/media/') ? 'vanilla-media/media' : 'vanilla-media/play';
            const relative = url.pathname.replace(/^\/media/, '');
            file = fs.readFileSync(root + decodeURIComponent(relative));
        }
        res.setHeader('Content-Type', ({ '.wasm': 'application/wasm', '.js': 'text/javascript', '.css': 'text/css', '.swf': 'application/x-shockwave-flash', '.xml': 'text/xml', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg' })[path.extname(url.pathname)] || 'application/octet-stream');
        res.end(file);
    } catch (error) {
        failures.push(url.pathname);
        res.writeHead(404).end();
    }
});
const websocketServer = new wsServer({server});
websocketServer.on('connection', socket => {
    socket.on('message', data => {
        const packet = data.toString();
        packets.push(packet);
        if (packet.includes('/version')) socket.send(Buffer.from('[S_VERSION]|FY15-20150206 (4954)r|\r\n'));
        // Match Snowflake's requirement: parse_qs must see the battleMode key.
        if (packet.includes('/place_context') && !packet.includes(' battleMode=')) {
            socket.send(Buffer.from('[S_LOGINDEBUG]|user code 900|\r\n'));
            socket.close();
        }
    });
});
(async () => {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    env.WEB_VANILLA_PLAY = `http://127.0.0.1:${server.address().port}`;
    env.WEB_VANILLA_MEDIA = env.WEB_VANILLA_PLAY + '/media';
    let browser;
    try {
        browser = await chromium.launch({ headless: true, args: ['--enable-unsafe-swiftshader'] });
        const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
        page.on('pageerror', error => errors.push(error.message));
        page.on('requestfailed', request => errors.push(`${request.url()}: ${request.failure().errorText}`));
        page.on('console', message => {
            if (probingSnow && /ERROR|Error #/.test(message.text())) errors.push(message.text());
        });
        await page.goto(`http://127.0.0.1:${server.address().port}/`);
        await page.waitForTimeout(3000);
        await page.evaluate(() => { location.hash = '/login'; });
        // Wait for the bootstrap, shell and server list rather than assuming load() means game ready.
        const deadline = Date.now() + 45000;
        while (!requests.includes('/media/play/v2/client/login.swf') && Date.now() < deadline) await page.waitForTimeout(250);
        probingSnow = true;
        await page.evaluate(() => window.snowball.loadMP({ snfSession: 'probe', pid: '108', worldName: 'cjsnow_0', data: 0, isMuted: false }));
        const snowDeadline = Date.now() + 20000;
        while (!packets.some(packet => packet.includes('/place_context')) && Date.now() < snowDeadline) await page.waitForTimeout(100);
        await page.waitForTimeout(500);
        fs.mkdirSync('.validation', { recursive: true });
        await page.screenshot({ path: '.validation/snow-transport.png' });
        const report = { requests, failures, errors, packets };
        fs.writeFileSync('.validation/snow-transport-report.json', JSON.stringify(report, null, 2));
        console.log(JSON.stringify({ packets, failures, errors }, null, 2));
        const context = packets.find(packet => packet.includes('/place_context'));
        assert(context, 'Snow must connect and send place_context');
        assert(context.includes(' battleMode=0&base_asset_url='), 'Snowflake requires decoded query fields on the socket');
        assert(!context.includes('battleMode%3D'), 'encoded query must not reach Snowflake');
        assert.equal(errors.length, 0, 'no Snow runtime errors before authentication');
        assert(requests.includes('/media/play/v2/client/club_penguin.swf'));
        assert(requests.includes('/media/play/web_service/environment_data.xml'));
        assert(requests.includes('/media/play/v2/client/login.swf'));
        assert(requests.includes('/servers.xml'));
    } finally {
        if (browser) await browser.close();
        websocketServer.close();
        server.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });

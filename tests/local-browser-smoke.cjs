// Uses only the disposable Docker fixture created by tests/local-stack.py.
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const { chromium } = require('../.validation/node_modules/playwright');
const meta = JSON.parse(fs.readFileSync('.validation/local-stack/meta.json', 'utf8'));
const base = `http://play.localhost:${meta.port}`;

(async () => {
    if (!meta.project.startsWith('wand-local-check-')) throw Error('Not a test project');
    execFileSync('docker', ['compose', '-p', meta.project, '-f', path.resolve('.validation/local-stack/compose.json'),
        'exec', '-T', 'db', 'psql', '-U', 'postgres', '-d', 'postgres', '-c', 'UPDATE room SET spawn=(id=100)'], {stdio:'pipe'});
    execFileSync('docker', ['compose', '-p', meta.project, '-f', path.resolve('.validation/local-stack/compose.json'),
        'up', '-d', '--no-deps', '--force-recreate', '--wait', 'houdini_blizzard'], {stdio:'pipe',timeout:90000});
    const catalogue = JSON.parse(fs.readFileSync('world_manager/catalog/manifest.json'));
    const marvel = catalogue.events.find(event => event.id === '2012-06-14-marvel-super-hero-takeover');
    const assetHash = marvel.rooms.find(room => room.room === '100').sha256;
    const executablePath = path.resolve('.validation/browsers/chromium-1194/chrome-win/chrome.exe');
    const browser = await chromium.launch({headless: true, executablePath,
        args: ['--host-resolver-rules=MAP *.localhost 127.0.0.1', '--enable-unsafe-swiftshader']});
    const page = await browser.newPage({viewport: {width: 1280, height: 1000}});
    const failures = [], errors = [], sockets = [], responses = [], consoleErrors = [];
    let joinedRoom = false;
    page.on('requestfailed', request => failures.push({url: request.url(), error: request.failure()?.errorText}));
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
    page.on('response', response => responses.push({url: response.url(), status: response.status()}));
    page.on('websocket', socket => {
        sockets.push(socket.url());
        socket.on('framereceived', event => {
            if (String(event.payload).includes('%xt%jr%')) joinedRoom = true;
        });
    });
    for (let attempt = 0; attempt < 20; attempt++) {
        await page.goto(`${base}/manager/login/`);
        if (await page.locator('[name=username]').count()) break;
        await page.waitForTimeout(1000);
    }
    await page.locator('[name=username]').fill('testmod');
    await page.locator('[name=password]').fill('FixturePass123!');
    await page.locator('button[type=submit],input[type=submit]').first().click();
    await page.waitForURL(`${base}/manager`);
    const accounts = JSON.parse(fs.readFileSync('.validation/local-stack/accounts.json'));
    for (const route of ['/manager/manage', `/manager/manage/${accounts.testmod}`, '/manager/verify/en', '/manager/password', '/manager/email']) {
        const result = await page.goto(base + route);
        if (result.status() !== 200) throw Error('Manager page failed: ' + route);
        await page.locator('.manager-header').waitFor();
        if (await page.locator('html').getAttribute('lang') !== 'en') throw Error('Manager language failed');
        await page.screenshot({path: '.validation/local-stack/' + route.replaceAll('/', '-') + '.png', fullPage:true});
    }
    await page.getByRole('link', {name: 'Online players'}).click();
    await page.locator('#online-status').filter({hasText: 'Last updated'}).waitFor();
    if (await page.locator('#online-servers span').count() !== 4) throw Error('Missing world status');
    await page.screenshot({path: '.validation/local-stack/manager-online.png', fullPage: true});
    await page.getByRole('link', {name: 'Rooms & events'}).click();
    await page.getByRole('heading', {name: 'Rooms & events', exact: true}).waitFor();
    await page.locator('select[name=asset]').selectOption(`catalog/${marvel.id}/100`);
    await page.getByRole('button', {name: 'Load preview', exact: true}).click();
    await page.frameLocator('#room-preview-frame').locator('ruffle-player').waitFor();
    await page.waitForTimeout(3000);
    await page.screenshot({path: '.validation/local-stack/manager-preview.png', fullPage: true});
    await page.getByRole('button', {name: `Activate ${marvel.name}`, exact: true}).click();
    await page.locator('.success').waitFor();
    await page.screenshot({path: '.validation/local-stack/manager-world.png', fullPage: true});
    await page.goto(base + '/');
    await page.locator('#penguin-login').click();
    await page.waitForResponse(response => response.url().includes('/client/login.swf') && response.ok(), {timeout: 60000});
    await page.waitForTimeout(5000);
    await page.screenshot({path: '.validation/local-stack/vanilla-live.png', fullPage: true});
    // Coordinates correspond to the original SWF's login fields at this fixed
    // viewport. These are real keyboard inputs, not injected game state.
    await page.mouse.click(650, 230);
    await page.keyboard.type('testmod');
    await page.mouse.click(650, 280);
    await page.keyboard.type('FixturePass123!');
    await page.mouse.click(650, 468);
    await page.waitForTimeout(12000);
    await page.screenshot({path: '.validation/local-stack/vanilla-auth.png', fullPage: true});
    await page.mouse.click(550, 300);
    await page.waitForTimeout(15000);
    await page.screenshot({path: '.validation/local-stack/vanilla-room.png', fullPage: true});
    const variantLoaded = responses.some(r => r.url.includes(`/rooms/town.swf?wand_asset=${assetHash}`) && r.status===200);
    const musicLoaded = responses.some(r => /\/music\/325\.swf[?]?/.test(r.url) && r.status===200);
    const legacyPaths = ['/social/autocomplete/v2/search/clientRules', '/web-service/membership', '/play//web_service/activate_player.php'];
    const known = url => legacyPaths.includes(new URL(url).pathname);
    const unexpectedFailures = failures.filter(f => !known(f.url));
    const unexpectedHttp = responses.filter(r => r.status >= 400 && !known(r.url) && !r.url.endsWith('/favicon.ico'));
    fs.writeFileSync('.validation/local-stack/browser-report.json', JSON.stringify({base, failures, errors, sockets, responses, joinedRoom, variantLoaded, musicLoaded, consoleErrors, unexpectedFailures, unexpectedHttp}, null, 2));
    console.log(JSON.stringify({manager: 'passed', failures: failures.length, errors, sockets, joinedRoom, variantLoaded, musicLoaded, consoleErrors}, null, 2));
    await browser.close();
    if (!joinedRoom) throw new Error('Ruffle did not receive a real room join');
    if (!variantLoaded || !musicLoaded) throw new Error('Ruffle did not load the selected room variant and music');
    if (errors.length || unexpectedFailures.length || unexpectedHttp.length) throw new Error('Unexpected browser or resource failure; inspect browser-report.json');
})().catch(error => { console.error(error); process.exit(1); });

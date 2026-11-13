// Visual-only catalogue preview check. Does not connect to or modify a game world.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {chromium} = require('../.validation/node_modules/playwright');
execFileSync(process.env.PYTHON || 'python', ['tests/render-catalog-fixture.py'], {stdio:'inherit'});
const manifest = JSON.parse(fs.readFileSync('world_manager/catalog/manifest.json', 'utf8'));
const previewTemplate = fs.readFileSync('world_manager/templates/manager/preview.html','utf8');
const posts = [];
const server = http.createServer((req,res) => {
    const url = new URL(req.url,'http://localhost');
    if (req.method !== 'GET') { posts.push(url.pathname); res.writeHead(405).end(); return; }
    try {
        let body, type='text/html';
        if (url.pathname === '/') body=fs.readFileSync('.validation/catalog-ui.html');
        else if (url.pathname.startsWith('/manager/world-static/')) {
            const file=path.basename(url.pathname);body=fs.readFileSync('world_manager/static/'+file);
            type=file.endsWith('.js')?'application/javascript':'text/css';
        } else if (url.pathname === '/manager/world/preview') {
            const asset=url.searchParams.get('asset');
            const event=manifest.events.find(e=>asset.startsWith('catalog/'+e.id+'/'));
            const room=event.rooms.find(r=>r.room===url.searchParams.get('room'));
            body=previewTemplate.replace('{{ room_name }}',room.room_key).replace('{{ source }}','/asset/'+room.sha256+'.swf');
        } else if (url.pathname.startsWith('/asset/')) {
            const file=path.basename(url.pathname);assert.match(file,/^[a-f0-9]{64}\.swf$/);
            body=fs.readFileSync('world_manager/catalog/assets/'+file);type='application/x-shockwave-flash';
        } else if (url.pathname.startsWith('/__wand/ruffle/')) {
            const file=path.basename(url.pathname);body=fs.readFileSync('web/ruffle/node_modules/@ruffle-rs/ruffle/'+file);
            type=file.endsWith('.wasm')?'application/wasm':'application/javascript';
        } else {res.writeHead(404).end();return;}
        res.setHeader('Content-Type',type);res.end(body);
    } catch(error) {res.writeHead(500).end(error.message);}
});
(async()=>{
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const browser=await chromium.launch({headless:true,executablePath:path.resolve('.validation/browsers/chromium-1194/chrome-win/chrome.exe'),args:['--enable-unsafe-swiftshader']});
    try {
        const page=await browser.newPage({viewport:{width:1440,height:1000}});
        const errors=[];page.on('pageerror',error=>errors.push(error.message));
        await page.goto('http://127.0.0.1:'+server.address().port);
        assert.equal(await page.locator('.event-card').count(),16);
        const design=page.locator('#room-design-form select[name=asset]');
        assert.equal(await design.locator('option').count(),14);
        await design.selectOption('catalog/2012-06-14-marvel-super-hero-takeover/100');
        assert.equal(await page.locator('#room-design-form select[name=music]').inputValue(),'325');
        await page.getByRole('button',{name:'Load preview',exact:true}).click();
        await page.frameLocator('#room-preview-frame').locator('ruffle-player').waitFor();
        await page.waitForTimeout(4000);
        await page.locator('#room-preview-frame').screenshot({path:'.validation/marvel-room-preview.png'});
        await page.screenshot({path:'.validation/catalog-manager-desktop.png',fullPage:true});
        await design.selectOption('catalog/2012-10-17-halloween-party/100');
        await page.getByRole('button',{name:'Load preview',exact:true}).click();
        await page.waitForTimeout(4000);
        await page.locator('#room-preview-frame').screenshot({path:'.validation/halloween-room-preview.png'});
        await page.setViewportSize({width:390,height:844});
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
        await page.screenshot({path:'.validation/catalog-manager-mobile.png',fullPage:true});
        assert.equal(posts.length,0,'Preview must not publish any changes');
        assert.deepEqual(errors, [], 'Preview must not produce JavaScript errors');
        console.log(JSON.stringify({events:16,townDesigns:13,posts:posts.length,errors},null,2));
    } finally {await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});

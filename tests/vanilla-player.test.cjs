const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/ruffle/vanilla.js', 'utf8');

function adapter(protocol = 'https:', media = 'https://media.example.test') {
    let loaded, rendered;
    const status = { setAttribute() {} };
    const target = { replaceWith(player) { rendered = player; } };
    const settings = { dataset: { media, address: 'game.example.test', loginPort: '7112', captcha: '',
        snowHost: 'snow.example.test', snowPort: '17002' } };
    const player = { style: {}, setAttribute() {}, ruffle: () => ({ load: async options => { loaded = options; } }) };
    const window = { RufflePlayer: { newest: () => ({ createPlayer: () => player }) }, swfobject: { ua: {} } };
    vm.runInNewContext(source, { window, URL, location: { protocol, href: `${protocol}//play.example.test/` },
        document: { createElement: () => status, getElementById: id => id === 'wand-vanilla-config' ? settings : target,
            body: { prepend() {} } }, console: { error() {} } });
    return { window, player, status, get loaded() { return loaded; }, get rendered() { return rendered; } };
}

test('Vanilla preserves original FlashVars, player ID and SWFObject callback', async () => {
    const state = adapter();
    const vars = { lang: 'es', play: 'https://media.example.test/play/', isAS3WebServicesOn: true, clientVersion: '21639' };
    let callback;
    assert.equal(state.window.swfobject.hasFlashPlayerVersion('12'), true);
    state.window.swfobject.embedSWF('https://media.example.test/play/v2/client/club_penguin.swf', 'flashClient',
        '100%', '100%', '12', null, vars, {}, { id: 'club_penguin', name: 'club_penguin', class: 'original-player' }, result => { callback = result; });
    await Promise.resolve();
    assert.equal(state.rendered.id, 'club_penguin');
    assert.equal(state.rendered.className, 'original-player');
    assert.equal(state.loaded.parameters, vars);
    assert.equal(state.loaded.socketProxy.length, 5);
    assert.equal(state.loaded.socketProxy[0].host, 'game.example.test');
    assert.equal(state.loaded.socketProxy[0].port, 7112);
    assert.equal(state.loaded.socketProxy[0].proxyUrl, 'wss://play.example.test/__wand/ws/login');
    assert.equal(state.loaded.allowScriptAccess, true);
    assert.equal(callback.success, true);
});
test('Vanilla rejects HTTP media on an HTTPS page', () => {
    const state = adapter('https:', 'http://media.example.test');
    assert.match(state.status.textContent, /HTTPS/);
    assert.equal(state.loaded, undefined);
});

test('Snow embeds with its own advertised host and port through same-origin WSS', async () => {
    const state = adapter();
    const vars = { mpProduct: 'cjsnow', snfSession: 'session-token', pid: 102 };
    state.window.swfobject.embedSWF('https://media.example.test/game/mpassets/playclients/r3662/flash_client_base_fp11.swf',
        'mpClient', '100%', '100%', '11.3', false, vars, {}, { id: 'mpClient' });
    await Promise.resolve();
    assert.equal(state.loaded.parameters, vars);
    assert.equal(state.loaded.socketProxy.length, 6);
    const snow = state.loaded.socketProxy[5];
    assert.equal(snow.host, 'snow.example.test');
    assert.equal(snow.port, 17002);
    assert.equal(snow.proxyUrl, 'wss://play.example.test/__wand/ws/snow');
    assert.equal(state.rendered.id, 'mpClient');
});

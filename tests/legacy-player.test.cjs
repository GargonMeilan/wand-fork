const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/ruffle/legacy.js', 'utf8');

async function boot(protocol = 'https:', media = 'https://legacy.example.test/media', runtime = true) {
    const status = { hidden: false };
    let options, listener, appended;
    const container = { dataset: { media, address: 'game.example.test', loginPort: '7112', language: 'es' },
        appendChild: player => { appended = player; } };
    const player = { setAttribute() {}, ruffle: () => ({ load: async value => { options = value; } }) };
    const window = { addEventListener: (_, fn) => { listener = fn; },
        RufflePlayer: runtime ? { newest: () => ({ createPlayer: () => player }) } : undefined };
    vm.runInNewContext(source, { window, URL, location: { protocol, href: `${protocol}//old.example.test/play/es/` },
        document: { getElementById: id => id === 'wand-game' ? container : id === 'wand-status' ? status : null }, console: { error() {} } });
    await listener();
    return { status, options, appended };
}

test('HTTPS uses WSS on the public play origin and maps all five exact sockets', async () => {
    const { status, options, appended } = await boot();
    assert.equal(status.hidden, true);
    assert.equal(appended.id, 'game');
    assert.equal(options.url, 'https://legacy.example.test/media/boots.swf');
    assert.equal(options.parameters.lang, 'es');
    assert.equal(options.allowScriptAccess, true);
    assert.equal('http://localhost/play/v2/client/load.swf'.replace(...options.urlRewriteRules[0]),
        'https://legacy.example.test/media/play/v2/client/load.swf');
    assert.deepEqual(Array.from(options.socketProxy, x => [x.host, x.port, x.proxyUrl]), [
        ['game.example.test', 7112, 'wss://old.example.test/__wand/ws/login'],
        ['game.example.test', 9875, 'wss://old.example.test/__wand/ws/blizzard'],
        ['game.example.test', 9876, 'wss://old.example.test/__wand/ws/glaciar'],
        ['game.example.test', 9877, 'wss://old.example.test/__wand/ws/avalanche'],
        ['game.example.test', 9878, 'wss://old.example.test/__wand/ws/yeti'],
    ]);
});
test('HTTP development uses WS and accepts a trailing slash on the media path', async () => {
    const { options } = await boot('http:', 'http://legacy.example.test/media/');
    assert.equal(options.url, 'http://legacy.example.test/media/boots.swf');
    assert.equal(options.socketProxy[0].proxyUrl, 'ws://old.example.test/__wand/ws/login');
});
test('mixed content is reported before loading the SWF', async () => {
    const { status, options } = await boot('https:', 'http://legacy.example.test');
    assert.equal(options, undefined);
    assert.match(status.textContent, /HTTPS/);
});
test('missing runtime produces a useful error', async () => {
    const { status } = await boot('https:', 'https://legacy.example.test', false);
    assert.match(status.textContent, /ruffle.js/);
});

const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/ruffle/world-notice.js', 'utf8');

function fixture() {
    let revision = 0, poll, reloads = 0, failure = false;
    const notices = [];
    const window = {
        fetch: async () => { if (failure) throw new Error('offline'); return {ok: true, json: async () => ({revision})}; },
        setInterval: fn => { poll = fn; }, location: {reload: () => { reloads++; }},
    };
    const document = {createElement: () => ({style: {}, setAttribute() {},
        append(...children) { this.children = children; }, addEventListener(_, fn) { this.click = fn; },
        remove() { this.removed = true; }}), body: {append: node => notices.push(node)}};
    vm.runInNewContext(source, {window, document, AbortSignal});
    return {notices, get reloads() { return reloads; }, set revision(value) { revision = value; },
        set failure(value) { failure = value; }, async poll() { await poll(); },
        async ready() { for (let i = 0; i < 4; i++) await Promise.resolve(); }};
}

test('world changes offer a reload without automatically interrupting players', async () => {
    const state = fixture(); await state.ready();
    await state.poll(); assert.equal(state.notices.length, 0);
    state.revision = 1; await state.poll();
    assert.equal(state.notices.length, 1); assert.equal(state.reloads, 0);
    await state.poll(); assert.equal(state.notices.length, 1);
    state.notices[0].children[1].click(); assert.equal(state.reloads, 1);
});

test('temporary failures preserve the running revision and never reload a game', async () => {
    const state = fixture(); await state.ready();
    state.failure = true; await state.poll(); assert.equal(state.notices.length, 0);
    state.failure = false; state.revision = 2; await state.poll();
    state.notices[0].children[2].click(); assert.equal(state.notices[0].removed, true);
    assert.equal(state.reloads, 0);
});

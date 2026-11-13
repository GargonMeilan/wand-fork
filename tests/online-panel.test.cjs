const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('world_manager/static/online.js', 'utf8');

function element() {
    return {value: '', textContent: '', children: [], listeners: {},
        append(...nodes) { this.children.push(...nodes); },
        replaceChildren(...nodes) { this.children = nodes; },
        addEventListener(type, handler) { this.listeners[type] = handler; }};
}
function fixture() {
    const elements = new Map();
    const get = id => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); };
    let offline = false, redirected = false, poll;
    const payload = {servers: [{id:3100,name:'blizzard',available:true,count:2},
        {id:3101,name:'glaciar',available:false,count:null}], players: [
        {id:7,username:'penguin',nickname:'Penguin',server_id:3100,server_name:'blizzard',
            room_kind:'room',room_id:100,room_name:'Town',client:'Vanilla',seconds_online:180},
        {id:8,username:'<script>alert(1)</script>',nickname:'Visitor',server_id:3100,server_name:'blizzard',
            room_kind:'igloo',room_id:42,owner_id:7,client:'Legacy',seconds_online:60}]};
    vm.runInNewContext(source, {
        document: {getElementById:get,createElement:element}, AbortSignal,
        Option: function(text,value) { return {text,value}; },
        window: {setInterval: fn => { poll = fn; }},
        fetch: async () => { if (offline) throw new Error('offline'); return {ok:true,redirected,json:async()=>payload}; },
    });
    return {get, async ready() { for (let i=0;i<6;i++) await Promise.resolve(); },
        async poll() { await poll(); }, set offline(value) { offline=value; }, set redirected(value) { redirected=value; }};
}

test('roster renders rooms, igloo owners and unavailable worlds with literal usernames', async () => {
    const state=fixture(); await state.ready();
    const rows=state.get('online-players').children;
    assert.equal(rows.length,2);
    assert.match(rows[0].children[2].textContent,/Town.*100/);
    assert.match(rows[1].children[2].textContent,/Igloo owned by #7/);
    assert.match(rows[1].children[0].textContent,/<script>/);
    assert.match(state.get('online-servers').children[1].textContent,/No recent data/);
});

test('search and server filters narrow the roster without another fetch', async () => {
    const state=fixture(); await state.ready();
    const search=state.get('online-search'); search.value='igloo'; search.listeners.input();
    assert.equal(state.get('online-players').children.length,1);
    assert.match(state.get('online-count').textContent,/1 of 2/);
    const server=state.get('online-server'); server.value='3101'; server.listeners.change();
    assert.match(state.get('online-count').textContent,/0 of 2/);
});

test('outages remove stale player rows and expired sessions show a login message', async () => {
    const state=fixture(); await state.ready();
    state.offline=true; await state.poll();
    assert.equal(state.get('online-players').children.length,0);
    state.offline=false; state.redirected=true; await state.poll();
    assert.match(state.get('online-status').textContent,/session expired/);
});

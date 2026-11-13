"use strict";
(() => {
    const status = document.getElementById("online-status");
    const body = document.getElementById("online-players");
    const serverList = document.getElementById("online-servers");
    const serverFilter = document.getElementById("online-server");
    const search = document.getElementById("online-search");
    const refresh = document.getElementById("online-refresh");
    let current, loading = false, receivedAt;
    function locationName(player) {
        if (player.room_kind === "igloo") return `Igloo owned by #${player.owner_id} (room ${player.room_id})`;
        if (player.room_kind === "backyard") return `Backyard owned by #${player.owner_id}`;
        return `${player.room_name}${player.room_id === null ? "" : ` (#${player.room_id})`}${player.room_kind === "game" ? " · Minigame" : ""}`;
    }
    function draw() {
        if (!current) return;
        const query = search.value.trim().toLocaleLowerCase();
        const players = current.players.filter(player =>
            (!serverFilter.value || String(player.server_id) === serverFilter.value) &&
            `${player.username} ${player.nickname} ${player.id} ${locationName(player)}`.toLocaleLowerCase().includes(query));
        body.replaceChildren();
        for (const player of players) {
            const row = document.createElement("tr");
            const values = [`${player.username} · #${player.id}${player.nickname !== player.username ? ` (${player.nickname})` : ""}`,
                player.server_name, locationName(player), player.client, `${Math.floor(player.seconds_online / 60)} min`];
            for (const value of values) {
                const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
            }
            body.append(row);
        }
        if (!players.length) {
            const row = document.createElement("tr"), cell = document.createElement("td"); cell.colSpan = 5;
            cell.textContent = "No players match these filters in worlds with recent data.";
            row.append(cell); body.append(row);
        }
        document.getElementById("online-count").textContent = `(${players.length} of ${current.players.length})`;
    }
    async function update() {
        if (loading) return;
        loading = true; refresh.disabled = true;
        try {
            const result = await fetch("/manager/online/data", {cache: "no-store", credentials: "same-origin", signal: AbortSignal.timeout(8000)});
            if (result.redirected || result.status === 403) throw new Error("Your session expired or no longer has permission. Return to the manager to sign in.");
            if (!result.ok) throw new Error("Presence could not be loaded. Retrying automatically.");
            current = await result.json(); receivedAt = Date.now();
            const selected = serverFilter.value;
            serverFilter.replaceChildren(new Option("All worlds", ""));
            serverList.replaceChildren();
            for (const server of current.servers) {
                serverFilter.append(new Option(server.name, String(server.id)));
                const label = document.createElement("span");
                label.textContent = `${server.name}: ${server.available ? `${server.count} online` : "No recent data"}`;
                serverList.append(label);
            }
            serverFilter.value = selected;
            status.textContent = `Last updated: ${new Date(receivedAt).toLocaleTimeString()}.`;
            draw();
        } catch (error) {
            // Do not keep presenting a stale roster as live during an outage.
            current = null; body.replaceChildren(); serverList.replaceChildren();
            document.getElementById("online-count").textContent = "";
            status.textContent = error.message;
        } finally { loading = false; refresh.disabled = false; }
    }
    search.addEventListener("input", draw);
    serverFilter.addEventListener("change", draw);
    refresh.addEventListener("click", update);
    update(); window.setInterval(update, 5000);
})();

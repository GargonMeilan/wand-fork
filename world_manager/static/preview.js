"use strict";
(() => {
    const container = document.getElementById("room-preview");
    const status = document.getElementById("preview-status");
    if (!window.RufflePlayer?.newest) { status.textContent = "The preview player could not be loaded."; return; }
    const player = window.RufflePlayer.newest().createPlayer();
    container.append(player);
    player.ruffle().load({url:container.dataset.source,allowScriptAccess:false,allowNetworking:"none",
        autoplay:"on",unmuteOverlay:"hidden",volume:0,scale:"showAll",backgroundColor:"#dce8f0",logLevel:"error"})
        .then(() => { status.textContent = "Visual preview · interactive elements may require the game engine"; })
        .catch(() => { status.textContent = "This room could not be previewed. It may require the game engine."; });
})();

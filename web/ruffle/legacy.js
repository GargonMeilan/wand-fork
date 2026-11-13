/* Ruffle's socketProxy matches the host/port requested by XMLSocket exactly. */
"use strict";
window.addEventListener("DOMContentLoaded", async () => {
    const container = document.getElementById("wand-game");
    const status = document.getElementById("wand-status");
    const sizeButton = document.getElementById("bigscreen");
    const languageSelect = document.getElementById("langselect");
    if (sizeButton) {
        const resize = (small) => {
            container.classList.toggle("wand-small", small);
            const icon = sizeButton.firstElementChild;
            if (icon) icon.id = icon.id.replace(/^(sm|big)/, small ? "big" : "sm");
        };
        resize(location.hash === "#small" || (window.getCookie && window.getCookie("size") === "small"));
        sizeButton.addEventListener("click", () => {
            const small = !container.classList.contains("wand-small");
            resize(small);
            location.hash = small ? "small" : "";
            if (window.setCookie) window.setCookie("size", small ? "small" : "big");
        });
    }
    if (languageSelect) {
        languageSelect.addEventListener("change", () => {
            const language = languageSelect.value.replace(/\//g, "");
            const play = new URL(container.dataset.play.replace(/\/$/, "") + "/");
            location.href = new URL(language ? `${language}/` : "./", play).href;
        });
    }
    try {
        if (!window.RufflePlayer || !window.RufflePlayer.newest) {
            throw new Error("No se ha podido cargar Ruffle. Revisa /__wand/ruffle/ruffle.js.");
        }
        const media = new URL(container.dataset.media.replace(/\/$/, "") + "/", location.href);
        if (location.protocol === "https:" && media.protocol !== "https:") {
            throw new Error("WEB_LEGACY_MEDIA debe utilizar HTTPS cuando el juego utiliza HTTPS.");
        }
        const host = container.dataset.address;
        const loginPort = Number(container.dataset.loginPort);
        const destinations = [[loginPort, "login"], [9875, "blizzard"],
            [9876, "glaciar"], [9877, "avalanche"], [9878, "yeti"]];
        const socketProxy = destinations.map(([port, name]) => {
            const url = new URL(`/__wand/ws/${name}`, location.href);
            url.protocol = location.protocol === "https:" ? "wss:" : "ws:";
            return { host, port, proxyUrl: url.href };
        });
        const player = window.RufflePlayer.newest().createPlayer();
        player.id = "game";
        player.setAttribute("name", "game");
        container.appendChild(player);
        await player.ruffle().load({
            url: new URL("boots.swf", media).href,
            // boots.swf accepts base to pass the full media prefix to shell.swf.
            parameters: { lang: container.dataset.language, base: media.href.replace(/\/$/, "") },
            base: media.href,
            // LocalConnection.domain() used by boots drops ports, and can return
            // localhost for IP hosts. Rewrite only its first loader to the exact
            // configured public media URL, without modifying the original SWF.
            urlRewriteRules: [[/^https?:\/\/[^/]+\/play\/v2\/client\/load\.swf$/, new URL("play/v2/client/load.swf", media).href]],
            socketProxy,
            allowScriptAccess: true, // grecaptchaSubmit / finishedCaptcha ExternalInterface callbacks
            autoplay: "on",
            unmuteOverlay: "visible",
            scale: "showAll",
            logLevel: "warn",
        });
        status.hidden = true;
    } catch (error) {
        console.error("Wand Legacy:", error);
        status.textContent = `No se ha podido iniciar el juego: ${error.message}`;
        status.hidden = false;
    }
});

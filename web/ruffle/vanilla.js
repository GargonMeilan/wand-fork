/* Keep the original Vanilla page, FlashVars and ExternalInterface callbacks. */
"use strict";
(() => {
    const settings = document.getElementById("wand-vanilla-config");
    const status = document.createElement("p");
    status.id = "wand-vanilla-status";
    status.setAttribute("role", "status");
    const fail = error => {
        console.error("Wand Vanilla:", error);
        status.textContent = `No se ha podido iniciar Vanilla: ${error.message}`;
        if (!status.isConnected) document.body.prepend(status);
    };
    try {
        if (!window.RufflePlayer?.newest || !window.swfobject) {
            throw new Error("No se ha podido cargar Ruffle o la página del cliente.");
        }
        const media = new URL(settings.dataset.media.replace(/\/$/, "") + "/");
        if (location.protocol === "https:" && media.protocol !== "https:") {
            throw new Error("WEB_VANILLA_MEDIA debe utilizar HTTPS.");
        }
        const socketProxy = [[Number(settings.dataset.loginPort), "login"], [9875, "blizzard"],
            [9876, "glaciar"], [9877, "avalanche"], [9878, "yeti"]].map(([port, name]) => {
            const proxy = new URL(`/__wand/ws/${name}`, location.href);
            proxy.protocol = location.protocol === "https:" ? "wss:" : "ws:";
            return { host: settings.dataset.address, port, proxyUrl: proxy.href };
        });
        // SWFObject's plugin check otherwise diverts the original page to the
        // Adobe installer before it ever attempts to embed the game.
        window.swfobject.hasFlashPlayerVersion = () => true;
        window.swfobject.getFlashPlayerVersion = () => ({ major: 32, minor: 0, release: 0 });
        window.swfobject.ua.pv = [32, 0, 0];
        window.swfobject.getObjectById = id => document.getElementById(id);
        window.swfobject.removeSWF = id => document.getElementById(id)?.remove();
        window.swfobject.embedSWF = (url, id, width, height, version, installer, flashVars, params, attributes, callback) => {
            const target = document.getElementById(id);
            if (!target) {
                fail(new Error(`No existe el contenedor ${id}.`));
                callback?.({ success: false, id });
                return;
            }
            const player = window.RufflePlayer.newest().createPlayer();
            // Snow embeds a separate SWF and connects to Snowflake, rather
            // than the Houdini world used by the main client and Water.
            let playerSockets = socketProxy;
            let parameters = flashVars;
            if (flashVars?.mpProduct === "cjsnow") {
                // MPClient URI-encodes this value for SWFObject's raw
                // flashvars string. Flash decoded that string once. Ruffle's
                // parameters object preserves values literally, so reproduce
                // that decode here or Snowflake rejects /place_context.
                if (typeof flashVars.queryString === "string") {
                    try {
                        parameters = { ...flashVars, queryString: decodeURIComponent(flashVars.queryString) };
                    } catch (error) {
                        fail(new Error("El contexto de Card-Jitsu Nieve tiene una codificación inválida."));
                        callback?.({ success: false, id });
                        return;
                    }
                }
                const host = settings.dataset.snowHost;
                const port = Number(settings.dataset.snowPort);
                if (!host || !Number.isInteger(port) || port < 1 || port > 65535) {
                    fail(new Error("SNOWFLAKE_HOST y SNOWFLAKE_PORT deben configurar Card-Jitsu Nieve."));
                    callback?.({ success: false, id });
                    return;
                }
                const proxy = new URL("/__wand/ws/snow", location.href);
                proxy.protocol = location.protocol === "https:" ? "wss:" : "ws:";
                playerSockets = [...socketProxy, { host, port, proxyUrl: proxy.href }];
            }
            player.id = attributes?.id || id;
            player.setAttribute("name", attributes?.name || player.id);
            if (attributes?.class) player.className = attributes.class;
            player.style.width = /^\d+$/.test(String(width)) ? `${width}px` : width;
            player.style.height = /^\d+$/.test(String(height)) ? `${height}px` : height;
            player.style.display = "block";
            target.replaceWith(player);
            player.ruffle().load({
                url: new URL(url, location.href).href,
                parameters,
                // The original client resolves ../web_service from its SWF.
                // Keep the SWF URL as base; the FlashVars carry full media paths.
                socketProxy: playerSockets,
                allowScriptAccess: true,
                autoplay: "on",
                unmuteOverlay: "visible",
                scale: "showAll",
                logLevel: "warn",
            }).then(() => callback?.({ success: true, id: player.id, ref: player })).catch(error => {
                fail(error);
                callback?.({ success: false, id: player.id });
            });
        };
        window.grecaptchaSubmit = () => {
            const player = document.querySelector("ruffle-player, ruffle-embed, ruffle-object");
            const finish = token => {
                if (typeof player?.finishedCaptcha === "function") player.finishedCaptcha(token);
            };
            if (settings.dataset.captcha) {
                window.grecaptcha.ready(() => window.grecaptcha.execute(settings.dataset.captcha, { action: "login" }).then(finish).catch(fail));
            } else finish("houdini");
        };
    } catch (error) {
        fail(error);
    }
})();

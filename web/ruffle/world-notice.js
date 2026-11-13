/* Room configuration is cached inside the Flash client until its next boot. */
"use strict";
(() => {
    if (typeof window.fetch !== "function") return;
    let initial;
    let checking = false;
    let displayed = false;
    async function check() {
        if (checking || displayed) return;
        checking = true;
        try {
            const result = await window.fetch("/__wand/world/revision", {
                cache: "no-store", credentials: "omit", signal: AbortSignal.timeout(8000),
            });
            if (!result.ok) return;
            const data = await result.json();
            if (!Number.isSafeInteger(data.revision) || data.revision < 0) return;
            if (initial === undefined) { initial = data.revision; return; }
            if (initial === data.revision) return;
            displayed = true;
            const notice = document.createElement("aside");
            notice.setAttribute("role", "status");
            notice.id = "wand-world-update";
            Object.assign(notice.style, { position: "fixed", top: "12px", left: "50%", transform: "translateX(-50%)",
                zIndex: "2147483647", background: "#fff3d9", color: "#163447", padding: "16px",
                border: "2px solid #b46d00", borderRadius: "8px", maxWidth: "90vw", font: "16px system-ui" });
            const text = document.createElement("p");
            text.textContent = "Han cambiado las decoraciones o la música. Recarga el juego para verlas; tendrás que iniciar sesión de nuevo.";
            const reload = document.createElement("button");
            reload.textContent = "Recargar juego";
            reload.addEventListener("click", () => window.location.reload());
            const dismiss = document.createElement("button");
            dismiss.textContent = "Más tarde";
            dismiss.style.marginLeft = "12px";
            dismiss.addEventListener("click", () => notice.remove());
            notice.append(text, reload, dismiss);
            document.body.append(notice);
        } catch (_) {
            // A temporary backend outage must never interrupt a game.
        } finally { checking = false; }
    }
    check();
    window.setInterval(check, 15000);
})();

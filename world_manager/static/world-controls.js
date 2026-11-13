"use strict";
document.querySelectorAll('select[name="asset"]').forEach(select => {
    select.addEventListener("change", () => {
        const music = select.selectedOptions[0]?.dataset.music;
        const target = select.form.querySelector('select[name="music"]');
        if (music !== undefined && target) target.value = music;
    });
});
document.getElementById("preview-room")?.addEventListener("click", () => {
    const form = document.getElementById("room-design-form");
    const url = new URL("/manager/world/preview", location.origin);
    url.searchParams.set("room", form.elements.room.value);
    url.searchParams.set("asset", form.elements.asset.value);
    const frame = document.getElementById("room-preview-frame");
    frame.src = url.href;
    frame.hidden = false;
    document.getElementById("preview-empty").hidden = true;
    document.getElementById("preview-description").textContent =
        form.elements.asset.selectedOptions[0].textContent + " · Preview only; no changes have been applied.";
});

"""Inventory dated path aliases and event classes inside bundled Vanilla SWFs.

This identifies evidence, never certifies a complete or playable event.
No external downloads or execution of SWF code are involved.
"""
import json
import re
import sys
import zlib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from world_manager.store import MAX_EXPANDED

MEDIA = ROOT / "vanilla-media"
CONFIG = MEDIA / "media/play/en/web_service/game_configs"
NAMES = {
    "rockhopperquest": "La búsqueda de Rockhopper", "puffle": "Fiesta de puffles",
    "aprilfools": "Día de las bromas", "earthday": "Día de la Tierra",
    "medieval": "Fiesta medieval", "superhero": "Superhéroes / Marvel",
    "musicjam": "Music Jam", "music": "Music Jam", "halloween": "Halloween",
    "holiday": "Navidad", "cfc": "Navidad / Coins for Change",
    "frozen": "Frozen", "muppets": "Los Muppets", "school": "Escuela y skate",
    "teenbeach": "Teen Beach Movie", "epfparty": "Operación EPF",
    "prehistoric": "Viaje a la prehistoria", "february": "SoundStudio (módulo February)",
    "automated": "Fiestas automatizadas", "june": "Misiones PSA (módulo June)",
    "epfhotsauce": "Operación Salsa Picante", "march": "Módulo March (edición por verificar)",
}
SKIP = {"common", "base", "ninja", "smoothie", "puffles"}
MISSING = {
    "superhero": "Identificar y reunir el conjunto de salas de esa edición, sus catálogos reales, módulo de fiesta, poderes, objetivos y validación de recompensas del servidor.",
    "music": "Verificar conciertos y dependencias, servicios de actuaciones, horarios, cookie específica y recompensas; las salas encontradas no acreditan el evento completo.",
    "frozen": "Verificar transformación/congelación, bolas de nieve, dependencias, cookie y tareas de Frozen, salas y catálogo de la misma edición.",
    "prehistoric": "Verificar transformaciones de dinosaurio, excavaciones, huevos, dependencias y recompensas; resolver IDs de salas no presentes en rooms.json.",
    "epfparty": "Verificar la edición exacta, salas solitarias, objetivos, navegación, servicio de fiesta y recompensas EPF.",
    "automated": "Verificar los ajustes y servicio esperados por AutomatedParty, fechas, tareas y recursos de una misma edición.",
}


def audit():
    groups = defaultdict(lambda: {"evidence": [], "references": [], "files": [], "classes": []})
    paths = json.loads((CONFIG / "paths.json").read_text(encoding="utf-8"))
    for scope, entries in paths.items():
        for alias, target in entries.items():
            match = re.match(r"w\.p(\d{4})\.([^.]+)\.", alias)
            if not match:
                continue
            date, module = match.groups()
            # Preserve the namespace literally; some historic keys are typos.
            key = ("p" + date, module)
            base = MEDIA / "media/play/v2/content" / ("global" if scope == "global" else "local/en")
            target_path = base / target
            exists = bool(target) and "%" not in target and target_path.is_file()
            groups[key]["references"].append({"alias": alias, "target": target, "exists": exists})
            groups[key]["evidence"].append(alias + " → " + (target or "(vacío)") +
                                           (" [archivo presente]" if exists else " [sin archivo exacto verificado]"))
    files = sorted((MEDIA / "media/play/v2/content/global/rooms").glob("*.swf"))
    files += sorted((MEDIA / "media/play/v2/client").glob("*.swf"))
    scanned = 0
    for file in files:
        body = file.read_bytes()
        if len(body) > MAX_EXPANDED:
            continue
        try:
            if body[:3] == b"CWS":
                decoder = zlib.decompressobj()
                body = decoder.decompress(body[8:], MAX_EXPANDED)
                if not decoder.eof:
                    continue
            elif body[:3] == b"FWS":
                body = body[8:]
            else:
                continue
        except zlib.error:
            continue
        scanned += 1
        matches = re.findall(rb"com\.clubpenguin\.world\.rooms(20\d{2})\.([A-Za-z0-9_]+)\.([A-Za-z0-9_.]+)", body)
        for year, module, symbol in sorted(set(matches)):
            module = module.decode("ascii")
            if module in SKIP:
                continue
            key = (year.decode("ascii"), module)
            rel = file.relative_to(ROOT).as_posix()
            if rel not in groups[key]["files"]:
                groups[key]["files"].append(rel)
                groups[key]["evidence"].append(rel + " :: " + symbol.decode("ascii"))
            groups[key]["classes"].append(symbol.decode("ascii"))
    # Item definitions are independent evidence, not proof of matching scenery.
    items = json.loads((CONFIG / "paper_items.json").read_text(encoding="utf-8"))
    marvel = [item for item in items if re.search(r"Iron Man|Captain America|Spider-Man|Loki|Thor Helmet|HULK BODYSUIT", item.get("label", ""), re.I)]
    groups[("p0612", "superhero")]["items"] = [{"id": item["paper_item_id"], "label": item["label"]} for item in marvel]
    groups[("p0612", "superhero")]["evidence"].append("paper_items.json: " + ", ".join(str(i["paper_item_id"]) + " " + i["label"] for i in marvel[:6]))
    events = []
    for (edition, module), data in sorted(groups.items()):
        event = {"id": edition + "-" + module, "name": NAMES.get(module, module) + " · " + edition,
                 "status": "Recursos parciales; evento completo sin verificar",
                 "full_activation_verified": False,
                 "notes": "Se encontraron {} referencias de configuración y {} SWF con clases del módulo. Los nombres genéricos como party.swf se reutilizan entre eventos: su alias no garantiza que el contenido corresponda a esta edición.".format(len(data["references"]), len(data["files"])),
                 "missing": MISSING.get(module, "Reunir y verificar salas, música, módulo de fiesta, dependencias, catálogos y protocolo del servidor de una misma edición; probar navegación, tareas y recompensas con el cliente real."),
                 **data}
        event["classes"] = sorted(set(event["classes"]))
        events.append(event)
    return {"method": "Dated aliases in paths.json and static namespace extraction from Vanilla room/client SWFs; item labels for Marvel. No gameplay certification or visual identification of all SWFs.",
            "swfs_scanned": scanned, "events": events}


if __name__ == "__main__":
    destination = ROOT / "world_manager/event-audit.json"
    content = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        if not destination.exists() or destination.read_text(encoding="utf-8") != content:
            sys.exit("Event audit is stale; run python scripts/audit-events.py")
    else:
        destination.write_text(content, encoding="utf-8", newline="\n")
    result = json.loads(content)
    print("{} SWFs examinados; {} grupos de eventos documentados; ninguno certificado completo.".format(result["swfs_scanned"], len(result["events"])))

"""Holt CardDefs.base.xml (Mechanik-Daten) aus HDTs HearthDb.dll, wenn sie fehlt oder veraltet ist."""
import glob
import logging
import os
import re
import struct

log = logging.getLogger("hscoach.extract")

HDT_APP_GLOB = os.path.join(os.environ.get("LOCALAPPDATA", ""), "HearthstoneDeckTracker", "app-*", "HearthDb.dll")


def _version_key(path):
    m = re.search(r"app-([\d.]+)", path)
    return tuple(int(x) for x in m.group(1).split(".") if x.isdigit()) if m else ()


def find_dll(pattern=HDT_APP_GLOB):
    dlls = sorted(glob.glob(pattern), key=_version_key)
    return dlls[-1] if dlls else None


def extract_base_xml(dll_path, out_path):
    """Sucht die eingebettete XML-Ressource (4-Byte-Laenge + Daten) und schreibt sie atomar nach out_path."""
    with open(dll_path, "rb") as f:
        data = f.read()
    for m in re.finditer(rb"<\?xml version", data):
        p = m.start()
        if p < 4:
            continue
        ln = struct.unpack("<I", data[p - 4:p])[0]
        blob = data[p:p + ln]
        if ln > 1_000_000 and blob.rstrip().endswith(b"</CardDefs>"):
            tmp = out_path + ".part"
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(tmp, "wb") as f:
                f.write(blob)
            os.replace(tmp, out_path)
            return True
    return False


def ensure_base_xml(cfg, dll_pattern=HDT_APP_GLOB):
    """True, wenn base.xml neu erzeugt wurde."""
    out = cfg["carddefs_base"]
    dll = find_dll(dll_pattern)
    if not dll:
        return False
    try:
        if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(dll):
            return False
        ok = extract_base_xml(dll, out)
        log.info("base.xml aus %s extrahiert: %s", dll, ok)
        return ok
    except Exception:
        log.exception("base.xml-Extraktion fehlgeschlagen")
        return False

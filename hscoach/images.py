"""Kartenportraits (voll, mit Rahmen) laden und cachen.

Download und Dekodieren passieren im Hintergrund; `PhotoImage` wird ausschliesslich im GUI-Thread erzeugt
(tkinter ist nicht thread-sicher).
"""
import logging
import os
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("hscoach.images")

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:  # Pillow ist optional
    PIL_OK = False

URL = "https://art.hearthstonejson.com/v1/render/latest/deDE/256x/{cid}.png"
RETRY_AFTER_S = 120


class ImageCache:
    def __init__(self, cfg):
        self.dir = cfg["images_dir"]
        try:
            os.makedirs(self.dir, exist_ok=True)
        except OSError:
            pass
        self._pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="img")
        self._failed = {}
        self._inflight = set()
        self._photos = {}
        self._lock = threading.Lock()

    def path(self, cid):
        return os.path.join(self.dir, f"{cid}.png")

    def have(self, cid):
        return os.path.exists(self.path(cid))

    def ensure(self, cids, on_ready):
        """Laedt fehlende Bilder im Hintergrund; on_ready(cid, ok) wird im Worker-Thread gerufen."""
        for cid in dict.fromkeys(c for c in cids if c):
            if self.have(cid):
                on_ready(cid, True)
                continue
            with self._lock:
                if cid in self._inflight or time.time() - self._failed.get(cid, 0) < RETRY_AFTER_S:
                    continue
                self._inflight.add(cid)
            self._pool.submit(self._download, cid, on_ready)

    def _download(self, cid, on_ready):
        ok = False
        try:
            req = urllib.request.Request(URL.format(cid=cid), headers={"User-Agent": "HSCoach/2.0"})
            data = urllib.request.urlopen(req, timeout=10).read()
            tmp = self.path(cid) + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, self.path(cid))
            ok = True
        except Exception as ex:
            log.info("Bild %s nicht ladbar: %s", cid, ex)
            self._failed[cid] = time.time()
        finally:
            with self._lock:
                self._inflight.discard(cid)
        try:
            on_ready(cid, ok)
        except Exception:
            log.exception("on_ready Fehler")

    def photo(self, cid, width, height):
        """GUI-Thread: PhotoImage fuer die Karte oder None."""
        if not PIL_OK or not cid:
            return None
        key = (cid, width, height)
        ph = self._photos.get(key)
        if ph is not None:
            return ph
        p = self.path(cid)
        if not os.path.exists(p):
            return None
        try:
            img = Image.open(p).convert("RGBA").resize((width, height), Image.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            self._photos[key] = ph
            return ph
        except Exception:
            log.exception("Bild %s defekt", cid)
            try:
                os.remove(p)
            except OSError:
                pass
            return None

"""A tiny helper inside Kings Analyzer. It shows the review pages from your KingsAnalyzer folder and lets the
review page save what you taught it straight into learned.json, so there is no file to move around.
Only answers this computer (127.0.0.1)."""
import json, os, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = 8137


def make_handler(docs, learned_path):
    lock = threading.Lock()

    def read_items():
        try:
            return json.load(open(learned_path, encoding="utf-8")).get("items", [])
        except Exception:
            return []

    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=docs, **k)

        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            b = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path.split("?")[0] == "/learned":
                with lock:
                    return self._json({"version": 1, "items": read_items()})
            return super().do_GET()

        def do_POST(self):
            if self.path.split("?")[0] != "/learned":
                return self._json({"ok": False}, 404)
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if n > 20_000_000:
                    return self._json({"ok": False}, 413)
                new = json.loads(self.rfile.read(n).decode("utf-8")).get("items", [])
                with lock:
                    have = {x.get("k"): x for x in read_items()}
                    for x in new:
                        if isinstance(x, dict) and x.get("k") and x.get("e"):
                            have[x["k"]] = x
                    tmp = learned_path + ".new"
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump({"version": 1, "items": list(have.values())}, f)
                    os.replace(tmp, learned_path)
                    return self._json({"ok": True, "n": len(have)})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 400)

    return H


def start(docs, learned_path, port=PORT):
    """Returns the port in use, or None if it could not start."""
    os.makedirs(docs, exist_ok=True)
    for p in (port, 0):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), make_handler(docs, learned_path))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv.server_address[1]
        except OSError:
            continue
    return None

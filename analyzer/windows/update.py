"""Brings this analyzer up to date from GitHub, without reinstalling anything.
Keeps your .venv, models, learned.json and results. Safe to run any time.
Usage: update.py [--quiet] [--from-dir PATH]   (--from-dir is for testing)"""
import hashlib, json, os, shutil, subprocess, sys, urllib.request

REPO = "rlahay-cloud/kings-hudl"
BRANCH = "main"
HERE = os.path.dirname(os.path.abspath(__file__))
ANALYZER = os.path.dirname(HERE)
ROOT = os.path.dirname(ANALYZER)
KEEP = {"learned.json", "error_log.txt"}
SKIP_DIRS = {"__pycache__", ".venv", "models", ".git"}
SKIP_EXT = {".pyc"}
quiet = "--quiet" in sys.argv


def say(s):
    if not quiet:
        print(s)


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "kings-analyzer-update"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if binary else json.loads(data.decode("utf-8"))


def list_remote(path):
    """All files under a folder of the repo: [(repo path, raw download url)]."""
    out = []
    for it in get("https://api.github.com/repos/%s/contents/%s?ref=%s" % (REPO, path, BRANCH)):
        if it["type"] == "dir":
            if it["name"] not in SKIP_DIRS:
                out += list_remote(it["path"])
        elif it["type"] == "file" and os.path.splitext(it["name"])[1] not in SKIP_EXT and it["name"] not in KEEP:
            out.append((it["path"], it["download_url"]))
    return out


def list_local(src):
    out = []
    base = os.path.join(src, "analyzer")
    for d, dirs, files in os.walk(base):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if os.path.splitext(f)[1] in SKIP_EXT or f in KEEP:
                continue
            p = os.path.join(d, f)
            out.append((os.path.relpath(p, src).replace(os.sep, "/"), p))
    rj = os.path.join(src, "roster.json")
    if os.path.exists(rj):
        out.append(("roster.json", rj))
    return out


def digest(p):
    return hashlib.sha1(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def main():
    src = sys.argv[sys.argv.index("--from-dir") + 1] if "--from-dir" in sys.argv else None
    try:
        files = list_local(src) if src else list_remote("analyzer") + [("roster.json", "https://raw.githubusercontent.com/%s/%s/roster.json" % (REPO, BRANCH))]
    except Exception as e:
        say("Could not reach GitHub (%s). Keeping what you have." % e)
        return 0
    req_before = digest(os.path.join(HERE, "requirements-windows.txt"))
    changed, failed = [], 0
    for rel, url in files:
        dest = os.path.join(ROOT, *rel.split("/"))
        try:
            data = open(url, "rb").read() if src else get(url, True)
        except Exception as e:
            failed += 1
            say("Could not get %s (%s)" % (rel, e))
            continue
        if os.path.exists(dest) and open(dest, "rb").read() == data:
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + ".new"
        open(tmp, "wb").write(data)
        os.replace(tmp, dest)
        changed.append(rel)
    say("Updated %d file(s)%s." % (len(changed), "" if not failed else ", %d could not be fetched" % failed))
    for c in changed:
        say("  " + c)
    if digest(os.path.join(HERE, "requirements-windows.txt")) != req_before:
        say("The list of parts changed. Installing them (a minute or two)...")
        py = os.path.join(ANALYZER, "windows", ".venv", "Scripts", "python.exe")
        if os.path.exists(py):
            subprocess.call([py, "-m", "pip", "install", "-r", os.path.join(HERE, "requirements-windows.txt")])
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Kings Film Room: GameSheet updater.

Opens GameSheet in a real browser window on this computer, clicks every Export
button for the division and for each team in it, saves the files, and sends the
division standings to Kings Film Room.

First version: the team page exports are saved to the "exports" folder next to
this file. If something does not work, the script saves what it saw into the
"debug" folder. Send that folder to Claude and it gets fixed.
"""
import datetime
import json
import re
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SETTINGS = HERE / "gamesheet_settings.json"
EXPORTS = HERE / "exports"
DEBUG = HERE / "debug"
PROFILE = HERE / "browser_profile"
DIVISION_URL = ("https://gamesheetstats.com/seasons/15454/standings"
                "?configuration%5Bcompact-view%5D=compact&filter%5Bdivision%5D=83415"
                "&filter%5Bquery%5D=&filter%5Bview%5D=divisions")
SUBMIT_URL = "https://kings-hudl-submit.r-lahay.workers.dev"
LOG = []


def say(msg):
    print(msg)
    LOG.append(msg)


def load_settings():
    s = {}
    if SETTINGS.exists():
        try:
            s = json.loads(SETTINGS.read_text(encoding="utf-8"))
        except Exception:
            s = {}
    if not s.get("passcode"):
        s["passcode"] = input("Type your Kings Film Room coach passcode and press Enter: ").strip()
        SETTINGS.write_text(json.dumps(s), encoding="utf-8")
    return s


def safe(name):
    return re.sub(r"[^A-Za-z0-9 _.-]+", "", name).strip().replace(" ", "_")[:60] or "team"


def debug_dump(page, tag):
    DEBUG.mkdir(exist_ok=True)
    try:
        (DEBUG / (tag + ".html")).write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(DEBUG / (tag + ".png")), full_page=True)
    except Exception as e:
        say("  could not save debug files: %s" % e)


def settle(page):
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except PWTimeout:
        pass
    page.wait_for_timeout(1500)


def export_buttons(page):
    return page.locator("button:has-text('Export'), a:has-text('Export'), [role=button]:has-text('Export')")


def download_all(page, folder, label):
    """Click every Export control on the page. Returns the saved file paths."""
    saved = []
    n = export_buttons(page).count()
    if n == 0:
        say("  %s: no Export button found" % label)
        return saved
    for i in range(n):
        try:
            btn = export_buttons(page).nth(i)
            with page.expect_download(timeout=30000) as dl:
                btn.click()
            d = dl.value
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / d.suggested_filename
            d.save_as(str(target))
            saved.append(target)
            say("  saved %s" % target.name)
        except Exception as e:
            say("  %s: export %d did not download (%s)" % (label, i + 1, str(e).splitlines()[0]))
    return saved


def send_standings(path, passcode):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    stamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if not text.lstrip().startswith("#updated="):
        text = "#updated=" + stamp + "\n" + text
    body = json.dumps({"passcode": passcode, "coach": "standings", "date": datetime.date.today().isoformat(),
                       "kind": "standings", "text": text}).encode("utf-8")
    req = urllib.request.Request(SUBMIT_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            j = json.loads(e.read().decode("utf-8"))
        except Exception:
            j = {"ok": False, "error": "HTTP %s" % e.code}
    except Exception as e:
        j = {"ok": False, "error": str(e)}
    return j


def team_links(page):
    links = {}
    for a in page.locator("a[href*='/teams/']").all():
        try:
            href = a.get_attribute("href") or ""
            m = re.search(r"/teams/(\d+)", href)
            name = (a.inner_text() or "").strip().splitlines()[0] if (a.inner_text() or "").strip() else ""
            if m and m.group(1) not in links:
                full = href if href.startswith("http") else "https://gamesheetstats.com" + href
                links[m.group(1)] = (name or "team_" + m.group(1), full)
        except Exception:
            pass
    return links


def main():
    s = load_settings()
    EXPORTS.mkdir(exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), headless=False, accept_downloads=True,
                                                   viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        say("Opening the division standings...")
        page.goto(DIVISION_URL)
        settle(page)
        files = download_all(page, EXPORTS / "division", "division")
        if files:
            say("Sending standings to Kings Film Room...")
            j = send_standings(files[0], s["passcode"])
            say("  Film Room says: " + ("standings updated" if j.get("ok") else "not sent: %s" % j.get("error")))
        else:
            debug_dump(page, "division_page")
            say("  No standings file. Page saved to the debug folder.")

        links = team_links(page)
        say("Found %d teams." % len(links))
        if not links:
            debug_dump(page, "division_page_no_teams")
        for tid, (name, url) in links.items():
            say("Team: %s" % name)
            try:
                page.goto(url)
                settle(page)
                folder = EXPORTS / safe(name)
                got = download_all(page, folder, name)
                # other pages of the same team (schedule, stats, roster and so on)
                base = re.search(r"(/teams/%s)" % tid, url).group(1)
                subs = set()
                for a in page.locator("a[href*='%s/']" % base).all():
                    h = (a.get_attribute("href") or "").split("#")[0].split("?")[0]
                    if h and h.rstrip("/").endswith(base) is False:
                        subs.add(h if h.startswith("http") else "https://gamesheetstats.com" + h)
                for sub in sorted(subs)[:8]:
                    page.goto(sub)
                    settle(page)
                    got += download_all(page, folder, name + " " + sub.rsplit("/", 1)[-1])
                if not got:
                    debug_dump(page, "team_" + safe(name))
            except Exception as e:
                say("  skipped: %s" % str(e).splitlines()[0])
        ctx.close()
    (HERE / "last_run.txt").write_text("\n".join(LOG), encoding="utf-8")
    say("Done. Team files are in the exports folder.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)

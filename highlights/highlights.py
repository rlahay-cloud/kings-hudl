"""Kings HUDL highlight video maker.

Reads the clip list that Kings HUDL already has for a game (every Kings goal, plus the clips
tagged Highlight in Coach's Corner), cuts those moments out of the full game video on this
computer, and joins them into one video. Nothing is uploaded.

Times in Kings HUDL are seconds into the main game video. If your video file starts at a
different moment than that one, use the offset (seconds to add to every time, can be negative).

Command line:
    python highlights.py 2026-10-18 "C:\\Videos\\game.mp4"
    python highlights.py 2026-10-18 game.mp4 --offset -12 --test
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

REPO = "rlahay-cloud/kings-hudl"
RAW = "https://raw.githubusercontent.com/%s/main/games/" % REPO
LEAD_GOAL, TAIL_GOAL = 10.0, 5.0
LEAD_CLIP, TAIL_CLIP = 2.0, 2.0
LEAD_POINT, TAIL_POINT = 5.0, 8.0
LEAD_SAVE, TAIL_SAVE = 4.0, 3.0
MAX_WIDTH = 1920


# ---------- the clip list from Kings HUDL ----------
def hms(text):
    m = re.match(r"^(\d+):(\d{2}):(\d{2})$", text.strip())
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kings-hudl-highlights"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def game_dates():
    """Dates that have a video review or clips on Kings HUDL, newest first."""
    names = json.loads(_get(RAW + "index.json"))
    dates = set()
    for n in names:
        m = re.match(r"^(?:review|clips)_(\d{4}-\d{2}-\d{2})", n)
        if m:
            dates.add(m.group(1))
    return sorted(dates, reverse=True)


def fetch_game_files(date, local_dir=None):
    """Returns {"review": [text, ...], "clips": [text, ...]} for the date."""
    if local_dir:
        names = sorted(os.listdir(local_dir))
        read = lambda n: open(os.path.join(local_dir, n), encoding="utf-8").read()
    else:
        names = json.loads(_get(RAW + "index.json"))
        read = lambda n: _get(RAW + n)
    out = {"review": [], "clips": []}
    for n in names:
        for kind in ("review", "clips"):
            if n.startswith("%s_%s" % (kind, date)) and n.endswith(".txt"):
                out[kind].append(read(n))
    return out


def players_text(field):
    nums = re.findall(r"[ai]?\d+", field or "", flags=re.I)
    main, assists = [], []
    for t in nums:
        n = re.sub(r"\D", "", t)
        if t[0].lower() == "i":
            continue
        if t[0].lower() == "a":
            if n not in assists:
                assists.append(n)
        elif n not in main:
            main.append(n)
    return main, assists


def collect(files):
    """Turns the files into a list of {sec, end, label, kind}."""
    items = []
    for text in files.get("review", []):
        for line in text.splitlines():
            a = line.split("|")
            if len(a) < 4:
                continue
            sec = hms(a[0])
            if sec is not None and a[1].strip() == "Against: Shot on goal":
                main, _ = players_text(a[2])
                items.append({"sec": float(sec), "end": None, "label": "Save" + (" #" + main[0] if main else ""), "kind": "save"})
                continue
            if sec is not None and a[1].strip() == "For: Goal":
                main, assists = players_text(a[2])
                scorer = [n for n in main if n not in assists]
                label = "Goal"
                if scorer:
                    label += " #" + scorer[0]
                if assists:
                    label += " (A " + ", ".join("#" + n for n in assists) + ")"
                items.append({"sec": float(sec), "end": None, "label": label, "kind": "goal"})
    for text in files.get("clips", []):
        for line in text.splitlines():
            a = line.split("|")
            if len(a) < 4:
                continue
            sec = hms(a[0])
            tag = a[1].strip()
            if sec is None or tag not in ("Goal", "Highlight"):
                continue
            end = None
            lab = a[3].strip()
            if len(a) > 4 and re.match(r"^\d{1,7}$", a[4].strip()):
                end = float(a[4].strip())
            main, assists = players_text(a[2])
            if tag == "Goal":
                scorer = [n for n in main if n not in assists]
                label = "Goal" + (" #" + scorer[0] if scorer else "")
                if assists:
                    label += " (A " + ", ".join("#" + n for n in assists) + ")"
                items.append({"sec": float(sec), "end": None, "label": label, "kind": "goal"})
            else:
                items.append({"sec": float(sec), "end": end if end and end > sec else None,
                              "label": lab or "Highlight", "kind": "clip"})
    return items


def segments(items, offset=0.0, video_len=None):
    """Start and end of each cut, in the video file's own time. Overlaps are joined."""
    segs = []
    for it in items:
        if it["kind"] == "goal":
            s, e = it["sec"] - LEAD_GOAL, it["sec"] + TAIL_GOAL
        elif it["kind"] == "save":
            s, e = it["sec"] - LEAD_SAVE, it["sec"] + TAIL_SAVE
        elif it["end"]:
            s, e = it["sec"] - LEAD_CLIP, it["end"] + TAIL_CLIP
        else:
            s, e = it["sec"] - LEAD_POINT, it["sec"] + TAIL_POINT
        s, e = s + offset, e + offset
        if e <= 0 or (video_len and s >= video_len):
            continue
        segs.append({"start": max(0.0, s), "end": min(e, video_len) if video_len else e, "label": it["label"]})
    segs.sort(key=lambda x: x["start"])
    merged = []
    for s in segs:
        if merged and s["start"] <= merged[-1]["end"] + 1.0:
            m = merged[-1]
            m["end"] = max(m["end"], s["end"])
            if s["label"] not in m["label"]:
                m["label"] += " / " + s["label"]
        else:
            merged.append(dict(s))
    return merged


# ---------- cutting and joining ----------
def find_ffmpeg(log=print):
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    log("Getting the video cutting program (one time, about a minute)...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "imageio-ffmpeg"],
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError("Could not get the video cutting program: %s" % e)


def find_font():
    for p in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(p):
            return p
    return None


def safe_text(t):
    return re.sub(r"[^A-Za-z0-9 #().,&/+-]", " ", t)[:70].strip()


def video_length(ffmpeg, video):
    p = subprocess.run([ffmpeg, "-i", video], stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True,
                       encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", p.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None


def cut_one(ffmpeg, video, seg, out, caption, font, log):
    vf = "scale='min(%d,iw)':-2" % MAX_WIDTH
    base = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", "%.2f" % seg["start"], "-i", video,
            "-t", "%.2f" % (seg["end"] - seg["start"])]
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-r", "24",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", out]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if caption and font:
        ff = font.replace("\\", "/").replace(":", "\\:")
        dt = ("drawtext=fontfile='%s':text='%s':fontcolor=white:fontsize=44:box=1:boxcolor=black@0.55:"
              "boxborderw=12:x=40:y=h-th-50" % (ff, safe_text(caption)))
        r = subprocess.run(base + ["-vf", vf + "," + dt] + enc, stderr=subprocess.PIPE, text=True,
                           encoding="utf-8", errors="replace", creationflags=flags)
        if r.returncode == 0:
            return
        log("Could not add the caption, cutting without it.")
    r = subprocess.run(base + ["-vf", vf] + enc, stderr=subprocess.PIPE, text=True,
                       encoding="utf-8", errors="replace", creationflags=flags)
    if r.returncode != 0:
        raise RuntimeError("The cutting program stopped: " + r.stderr.strip()[-300:])


def make_video(video, date, out, offset=0.0, test=False, local_dir=None, log=print, progress=None, saves=True):
    files = fetch_game_files(date, local_dir)
    items = [i for i in collect(files) if saves or i["kind"] != "save"]
    if not items:
        raise RuntimeError("Kings HUDL has no goals or highlight clips for %s yet." % date)
    ffmpeg = find_ffmpeg(log)
    dur = video_length(ffmpeg, video)
    segs = segments(items, offset, dur)
    if not segs:
        raise RuntimeError("None of the clips fall inside this video. Check the offset.")
    if test:
        segs = segs[:1]
    total = sum(s["end"] - s["start"] for s in segs)
    log("%d clips, %d minutes %d seconds in all." % (len(segs), total // 60, total % 60))
    font = find_font()
    tmp = tempfile.mkdtemp(prefix="kings_hl_")
    try:
        names = []
        for i, s in enumerate(segs):
            log("Cutting clip %d of %d: %s" % (i + 1, len(segs), s["label"]))
            fn = os.path.join(tmp, "c%03d.mp4" % i)
            cut_one(ffmpeg, video, s, fn, s["label"], font, log)
            names.append(fn)
            if progress:
                progress(i + 1, len(segs))
        lst = os.path.join(tmp, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for n in names:
                f.write("file '%s'\n" % n.replace("\\", "/").replace("'", "'\\''"))
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        log("Joining the clips.")
        r = subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                            "-i", lst, "-c", "copy", "-movflags", "+faststart", out], stderr=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            raise RuntimeError("Could not join the clips: " + r.stderr.strip()[-300:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log("Done: " + out)
    return out


def main():
    ap = argparse.ArgumentParser(description="Make a Kings highlight video from Kings HUDL clips.")
    ap.add_argument("date", help="Game date, like 2026-10-18")
    ap.add_argument("video", help="The full game video file")
    ap.add_argument("--offset", type=float, default=0.0, help="Seconds to add to every Kings HUDL time")
    ap.add_argument("--test", action="store_true", help="Only make the first clip, to check the timing")
    ap.add_argument("--no-saves", action="store_true", help="Leave out the saves (shots against)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--local-dir", default=None, help="Read the game files from a folder instead of GitHub")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.expanduser("~"), "Documents", "KingsHighlights",
                                "Kings_highlights_%s%s.mp4" % (a.date, "_test" if a.test else ""))
    make_video(a.video, a.date, out, a.offset, a.test, a.local_dir, saves=not a.no_saves)


if __name__ == "__main__":
    main()

"""Kings HUDL Game Analyzer, Windows window.

Pick the game video, press Start. It reads the video from your computer (no upload), shows how
long is left, keeps the computer awake, and opens the review page when it is done.
Only uses what comes with Python, so it starts fast.
"""
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ANALYZER = os.environ.get("KINGS_ANALYZER_SCRIPT") or os.path.join(os.path.dirname(HERE), "kings_analyzer.py")
RINK = os.path.join(os.path.dirname(HERE), "rinks", "ingredion_rink1.json")
MODELS = os.path.join(HERE, "models")
DOCS = os.path.join(os.path.expanduser("~"), "Documents", "KingsAnalyzer")
PROG = re.compile(r"^(\d+) of (\d+) seconds of video done\. ([\d.]+) s of work per second of video\. About (\d+) minutes left")


def keep_awake(on):
    """Stop Windows from sleeping while the analysis runs (it can take hours)."""
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except Exception:
        pass


def video_info(path):
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if w <= 0 or not fps:
            return None
        return w, h, frames / fps
    except Exception:
        return None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kings HUDL Game Analyzer")
        self.geometry("760x640")
        self.minsize(640, 560)
        self.proc = None
        self.video = None
        self.dur = 0.0
        self.outdir = None
        self.running = False
        self.q = queue.Queue()
        self.t_start = self.t_end = 0.0
        pad = {"padx": 12, "pady": 6}

        tk.Label(self, text="Kings HUDL Game Analyzer", font=("Segoe UI", 16, "bold")).pack(anchor="w", **pad)

        f1 = ttk.LabelFrame(self, text="1. The game video")
        f1.pack(fill="x", **pad)
        self.btn_pick = ttk.Button(f1, text="Choose video...", command=self.pick)
        self.btn_pick.pack(side="left", padx=8, pady=8)
        self.lbl_video = tk.Label(f1, text="No video chosen yet", anchor="w", justify="left")
        self.lbl_video.pack(side="left", fill="x", expand=True, padx=8)

        f2 = ttk.LabelFrame(self, text="2. How much of the game")
        f2.pack(fill="x", **pad)
        self.how = tk.StringVar(value="test")
        ttk.Radiobutton(f2, text="Test: the first 5 minutes (do this first)", variable=self.how, value="test").pack(anchor="w", padx=8)
        ttk.Radiobutton(f2, text="The whole game", variable=self.how, value="all").pack(anchor="w", padx=8)
        row = tk.Frame(f2)
        row.pack(anchor="w", padx=8, pady=(0, 6))
        ttk.Radiobutton(row, text="From minute", variable=self.how, value="range").pack(side="left")
        self.e_from = ttk.Entry(row, width=5)
        self.e_from.insert(0, "0")
        self.e_from.pack(side="left", padx=4)
        tk.Label(row, text="to minute").pack(side="left")
        self.e_to = ttk.Entry(row, width=5)
        self.e_to.insert(0, "10")
        self.e_to.pack(side="left", padx=4)

        f3 = ttk.LabelFrame(self, text="3. Speed")
        f3.pack(fill="x", **pad)
        self.speed = tk.StringVar(value="normal")
        ttk.Radiobutton(f3, text="Normal (best at finding small players)", variable=self.speed, value="normal").pack(anchor="w", padx=8)
        ttk.Radiobutton(f3, text="Quick (about twice as fast, misses a few far players)", variable=self.speed, value="quick").pack(anchor="w", padx=8)
        self.nums = tk.BooleanVar(value=False)
        ttk.Checkbutton(f3, text="Also try to read jersey numbers on close up players (adds a lot of time, only a hint)", variable=self.nums).pack(anchor="w", padx=8, pady=(4, 6))
        self.fresh = tk.BooleanVar(value=True)
        ttk.Checkbutton(f3, text="Start over (delete earlier results for this video and settings)", variable=self.fresh).pack(anchor="w", padx=8, pady=(0, 6))

        f4 = tk.Frame(self)
        f4.pack(fill="x", **pad)
        self.btn_go = ttk.Button(f4, text="Start", command=self.start)
        self.btn_go.pack(side="left")
        self.btn_old = ttk.Button(f4, text="Open earlier results...", command=self.open_old)
        self.btn_old.pack(side="left", padx=8)
        self.btn_hl = ttk.Button(f4, text="Make highlight video...", command=self.open_highlights)
        self.btn_hl.pack(side="left", padx=8)

        self.bar = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.bar.pack(fill="x", padx=12, pady=(8, 2))
        self.lbl_status = tk.Label(self, text="Ready.", anchor="w", justify="left", wraplength=720)
        self.lbl_status.pack(fill="x", padx=12)
        self.log = tk.Text(self, height=9, state="disabled", wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        os.makedirs(DOCS, exist_ok=True)
        os.makedirs(MODELS, exist_ok=True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(150, self.pump)

    # ---- helpers ----
    def say(self, text):
        self.lbl_status.config(text=text)

    def add_log(self, line):
        self.log.config(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def pick(self):
        p = filedialog.askopenfilename(title="Choose the game video",
                                       filetypes=[("Video", "*.mov *.mp4 *.mkv *.m4v *.avi"), ("All files", "*.*")])
        if not p:
            return
        info = video_info(p)
        if not info:
            messagebox.showerror("Kings Analyzer", "That file could not be opened as a video. It may still be copying. Try again in a minute.")
            return
        self.video = p
        w, h, dur = info
        self.dur = dur
        self.lbl_video.config(text="%s\n%d by %d, %.0f minutes long" % (os.path.basename(p), w, h, dur / 60.0))
        self.e_to.delete(0, "end")
        self.e_to.insert(0, str(int(dur // 60)))
        if w < 3000:
            self.say("Note: this video is only %d pixels wide. The program was set up for the big panorama (about 4080 wide), so results may be poor." % w)
        else:
            self.say("Ready. Do the 5 minute test first and watch the minutes left.")

    def window(self):
        mode = self.how.get()
        if mode == "test":
            return 0.0, min(300.0, self.dur)
        if mode == "all":
            return 0.0, self.dur
        try:
            a = float(self.e_from.get()) * 60.0
            b = float(self.e_to.get()) * 60.0
        except ValueError:
            return None
        if b <= a:
            return None
        return a, min(b, self.dur)

    def run_dir(self, a, b):
        base = os.path.splitext(os.path.basename(self.video))[0]
        tag = "%s_%d-%d_%s" % (base, a // 60, b // 60, self.speed.get())
        return os.path.join(DOCS, re.sub(r"[^\w.-]+", "_", tag))

    # ---- run ----
    def start(self):
        if self.running:
            self.stop()
            return
        if not self.video:
            messagebox.showinfo("Kings Analyzer", "Choose the game video first.")
            return
        win = self.window()
        if not win:
            messagebox.showinfo("Kings Analyzer", "Check the minutes. The end must be after the start.")
            return
        a, b = win
        self.t_start, self.t_end = a, b
        self.outdir = self.run_dir(a, b)
        if self.fresh.get() and os.path.isdir(self.outdir):
            for fn in os.listdir(self.outdir):
                fp = os.path.join(self.outdir, fn)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except OSError:
                        pass
        os.makedirs(self.outdir, exist_ok=True)
        imgsz = "1280" if self.speed.get() == "normal" else "960"
        cmd = [sys.executable, "-u", ANALYZER, "analyze", self.video, self.outdir, "--rink", RINK,
               "--start", str(a), "--end", str(b), "--step", "2", "--imgsz", imgsz, "--model", "yolov8s.pt"]
        if self.nums.get():
            cmd.append("--numbers")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.proc = subprocess.Popen(cmd, cwd=MODELS, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, encoding="utf-8", errors="replace", env=env, creationflags=flags)
        except Exception as e:
            messagebox.showerror("Kings Analyzer", "Could not start: %s" % e)
            return
        self.running = True
        keep_awake(True)
        self.btn_go.config(text="Stop")
        self.btn_pick.config(state="disabled")
        self.bar["value"] = 0
        self.say("Starting. The first minute is loading programs.")
        self.add_log("Results go to: " + self.outdir)
        threading.Thread(target=self.read_output, daemon=True).start()

    def read_output(self):
        for line in self.proc.stdout:
            self.q.put(("line", line.rstrip()))
        self.q.put(("done", self.proc.wait()))

    def pump(self):
        """Runs on the window's own thread: take what the reader thread collected and show it."""
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "line":
                    self.on_line(val)
                else:
                    self.finished(val)
        except queue.Empty:
            pass
        self.after(150, self.pump)

    def on_line(self, line):
        if not line or "Warning" in line or "super().__init__" in line or "w_ih" in line:
            return
        m = PROG.match(line)
        if m:
            t, tot, per, mins = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4))
            span = max(1.0, self.t_end - self.t_start)
            self.bar["value"] = max(0, min(100, 100.0 * (t - self.t_start) / span))
            left = ("about %d minutes left" % mins) if mins >= 1 else "less than a minute left"
            self.say("%d of %d minutes of video read, %s." % (t // 60, tot // 60, left))
            self.add_log(line)
            return
        self.add_log(line)
        if line.startswith(("Loading", "Ready", "Building", "Numbers", "Found results", "Carrying")):
            self.say(line)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.say("Stopping. Next time, untick Start over to carry on from here.")

    def finished(self, code):
        self.running = False
        keep_awake(False)
        self.btn_go.config(text="Start")
        self.btn_pick.config(state="normal")
        page = os.path.join(self.outdir, "review.html") if self.outdir else ""
        if code == 0 and os.path.exists(page):
            self.bar["value"] = 100
            self.fresh.set(True)
            self.say("Done. Opening the review page. Choose the game video there when it asks.")
            self.add_log("Review page: " + page)
            webbrowser.open("file:///" + page.replace("\\", "/"))
            try:
                os.startfile(self.outdir)
            except Exception:
                pass
        else:
            self.fresh.set(False)
            self.say("It stopped before it finished. Press Start with Start over unticked to carry on, or send the lines in the box to Claude.")

    def open_old(self):
        p = filedialog.askopenfilename(title="Choose a review.html from an earlier run", initialdir=DOCS,
                                       filetypes=[("Review page", "review.html"), ("Web page", "*.html")])
        if p:
            webbrowser.open("file:///" + p.replace("\\", "/"))

    def open_highlights(self):
        if getattr(self, "hl_win", None) and self.hl_win.winfo_exists():
            self.hl_win.lift()
            return
        self.hl_win = HighlightWindow(self)

    def on_close(self):
        if self.running and not messagebox.askyesno("Kings Analyzer", "It is still working. Stop it and close?"):
            return
        self.stop()
        keep_awake(False)
        self.destroy()


class HighlightWindow(tk.Toplevel):
    """Cuts the Kings goals and Highlight clips from Kings HUDL out of the game video and joins them."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Highlight video")
        self.geometry("640x560")
        self.q = queue.Queue()
        self.busy = False
        pad = {"padx": 12, "pady": 6}
        tk.Label(self, text="Highlight video from Kings HUDL", font=("Segoe UI", 14, "bold")).pack(anchor="w", **pad)
        tk.Label(self, justify="left", anchor="w", wraplength=600,
                 text="Uses every Kings goal plus the clips you tagged Highlight in Coach's Corner. "
                      "It cuts them out of the full game video on this computer and joins them in game order.").pack(fill="x", padx=12)
        f1 = ttk.LabelFrame(self, text="1. Game video")
        f1.pack(fill="x", **pad)
        ttk.Button(f1, text="Choose video...", command=self.pick).pack(side="left", padx=8, pady=8)
        self.video = app.video
        self.lbl = tk.Label(f1, text=os.path.basename(self.video) if self.video else "No video chosen yet", anchor="w")
        self.lbl.pack(side="left", fill="x", expand=True, padx=8)
        f2 = ttk.LabelFrame(self, text="2. Which game")
        f2.pack(fill="x", **pad)
        self.date = tk.StringVar()
        self.cb = ttk.Combobox(f2, textvariable=self.date, width=14)
        self.cb.pack(side="left", padx=8, pady=8)
        self.lbl_dates = tk.Label(f2, text="Loading the games from Kings HUDL...", anchor="w")
        self.lbl_dates.pack(side="left", padx=8)
        f3 = ttk.LabelFrame(self, text="3. Timing (leave at 0 unless the clips start at the wrong moment)")
        f3.pack(fill="x", **pad)
        tk.Label(f3, text="Seconds to add:").pack(side="left", padx=8, pady=8)
        self.off = ttk.Entry(f3, width=7)
        self.off.insert(0, "0")
        self.off.pack(side="left")
        tk.Label(f3, text="  (use a minus, like -12, if the clips start too late)").pack(side="left")
        f4 = tk.Frame(self)
        f4.pack(fill="x", **pad)
        self.b_test = ttk.Button(f4, text="Test the first clip", command=lambda: self.go(True))
        self.b_test.pack(side="left")
        self.b_all = ttk.Button(f4, text="Make the highlight video", command=lambda: self.go(False))
        self.b_all.pack(side="left", padx=8)
        self.bar = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.bar.pack(fill="x", padx=12, pady=(6, 2))
        self.log = tk.Text(self, height=10, state="disabled", wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        threading.Thread(target=self.load_dates, daemon=True).start()
        self.after(150, self.pump)

    def add_log(self, line):
        self.log.config(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def pick(self):
        p = filedialog.askopenfilename(title="Choose the game video",
                                       filetypes=[("Video", "*.mov *.mp4 *.mkv *.m4v *.avi"), ("All files", "*.*")])
        if p:
            self.video = p
            self.lbl.config(text=os.path.basename(p))

    def load_dates(self):
        try:
            import highlights
            self.q.put(("dates", highlights.game_dates()))
        except Exception as e:
            self.q.put(("dates_err", str(e)))

    def go(self, test):
        if self.busy:
            return
        if not self.video:
            messagebox.showinfo("Highlight video", "Choose the game video first.", parent=self)
            return
        date = self.date.get().strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            messagebox.showinfo("Highlight video", "Pick the game date, like 2026-10-18.", parent=self)
            return
        try:
            off = float(self.off.get().strip() or "0")
        except ValueError:
            messagebox.showinfo("Highlight video", "Seconds to add must be a number, like 0 or -12.", parent=self)
            return
        out = os.path.join(DOCS, "Highlights", "Kings_highlights_%s%s.mp4" % (date, "_test" if test else ""))
        self.busy = True
        self.bar["value"] = 0
        self.b_test.config(state="disabled")
        self.b_all.config(state="disabled")
        keep_awake(True)
        threading.Thread(target=self.work, args=(date, off, test, out), daemon=True).start()

    def work(self, date, off, test, out):
        try:
            import highlights
            highlights.make_video(self.video, date, out, off, test, None,
                                  log=lambda t: self.q.put(("line", t)),
                                  progress=lambda i, n: self.q.put(("bar", 100.0 * i / n)))
            self.q.put(("done", out))
        except Exception as e:
            self.q.put(("fail", str(e)))

    def pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "line":
                    self.add_log(val)
                elif kind == "bar":
                    self.bar["value"] = val
                elif kind == "dates":
                    self.cb["values"] = val
                    if val and not self.date.get():
                        self.date.set(val[0])
                    self.lbl_dates.config(text="Pick the game, or type a date.")
                elif kind == "dates_err":
                    self.lbl_dates.config(text="Could not load the list (no internet?). Type the date, like 2026-10-18.")
                elif kind in ("done", "fail"):
                    self.busy = False
                    keep_awake(False)
                    self.b_test.config(state="normal")
                    self.b_all.config(state="normal")
                    if kind == "done":
                        self.bar["value"] = 100
                        self.add_log("Opening the video.")
                        try:
                            os.startfile(val)
                        except Exception:
                            pass
                    else:
                        self.add_log("Stopped: " + val)
                        messagebox.showerror("Highlight video", val, parent=self)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(150, self.pump)


if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception:
        import traceback
        text = traceback.format_exc()
        try:
            with open(os.path.join(HERE, "error_log.txt"), "w") as f:
                f.write(text)
        except Exception:
            pass
        try:
            messagebox.showerror("Kings Analyzer", "The window could not start. Details were saved in error_log.txt next to this program.\n\n" + text[-600:])
        except Exception:
            pass

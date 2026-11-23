"""Kings Film Room Highlight Video maker, its own small Windows program.

Cuts the Kings goals and Highlight clips that Kings Film Room has for a game out of the full game video
on this computer and joins them into one video. Nothing is uploaded.
"""
import os
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DOCS = os.path.join(os.path.expanduser("~"), "Documents", "KingsHighlights")


def keep_awake(on):
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except Exception:
        pass


class App(tk.Tk):
    """Cuts the Kings goals and Highlight clips from Kings Film Room out of the game video and joins them."""

    def __init__(self):
        super().__init__()
        self.title("Kings Highlight Video")
        self.geometry("700x900")
        self.minsize(640, 780)
        self.q = queue.Queue()
        self.busy = False
        pad = {"padx": 12, "pady": 6}
        tk.Label(self, text="Highlight video from Kings Film Room", font=("Segoe UI", 14, "bold")).pack(anchor="w", **pad)
        tk.Label(self, justify="left", anchor="w", wraplength=600,
                 text="Uses every Kings goal plus the clips you tagged Highlight in Coach's Corner. "
                      "It cuts them out of the full game video on this computer and joins them in game order.").pack(fill="x", padx=12)
        f1 = ttk.LabelFrame(self, text="1. Game video")
        f1.pack(fill="x", **pad)
        ttk.Button(f1, text="Choose video...", command=self.pick).pack(side="left", padx=8, pady=8)
        self.video = None
        self.lbl = tk.Label(f1, text=os.path.basename(self.video) if self.video else "No video chosen yet", anchor="w")
        self.lbl.pack(side="left", fill="x", expand=True, padx=8)
        f2 = ttk.LabelFrame(self, text="2. Which game")
        f2.pack(fill="x", **pad)
        self.date = tk.StringVar()
        self.cb = ttk.Combobox(f2, textvariable=self.date, width=14)
        self.cb.pack(side="left", padx=8, pady=8)
        self.lbl_dates = tk.Label(f2, text="Loading the games from Kings Film Room...", anchor="w")
        self.lbl_dates.pack(side="left", padx=8)
        f3 = ttk.LabelFrame(self, text="3. Timing (leave at 0 unless the clips start at the wrong moment)")
        f3.pack(fill="x", **pad)
        tk.Label(f3, text="Seconds to add:").pack(side="left", padx=8, pady=8)
        self.off = ttk.Entry(f3, width=7)
        self.off.insert(0, "0")
        self.off.pack(side="left")
        tk.Label(f3, text="  (use a minus, like -12, if the clips start too late)").pack(side="left")
        self.f_ang = ttk.LabelFrame(self, text="Extra camera angles (optional)")
        self.f_ang.pack(fill="x", **pad)
        self.ang_info = tk.Label(self.f_ang, anchor="w", justify="left", wraplength=580,
                                 text="Pick a game and its extra cameras show here.")
        self.ang_info.pack(fill="x", padx=8, pady=6)
        self.ang_rows = tk.Frame(self.f_ang)
        self.ang_rows.pack(fill="x", padx=8)
        self.ang_files = {}
        self.attack = tk.StringVar()
        self.slow = tk.BooleanVar(value=False)
        self.zoom = tk.StringVar(value="No zoom")
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.load_angles())
        self.cb.bind("<FocusOut>", lambda e: self.load_angles())
        f5 = ttk.LabelFrame(self, text="Clips to include (tick the ones you want)")
        f5.pack(fill="both", expand=True, **pad)
        top = tk.Frame(f5)
        top.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(top, text="Show:").pack(side="left")
        self.flt = tk.StringVar(value="Goals and highlights")
        self.flt_cb = ttk.Combobox(top, textvariable=self.flt, state="readonly", width=24,
                                   values=["Goals and highlights", "Everything", "Goals", "Saves", "Shots"])
        self.flt_cb.pack(side="left", padx=6)
        self.flt_cb.bind("<<ComboboxSelected>>", lambda e: self.draw_picks())
        ttk.Button(top, text="Tick all shown", command=lambda: self.tick_shown(True)).pack(side="left", padx=(8, 2))
        ttk.Button(top, text="Clear shown", command=lambda: self.tick_shown(False)).pack(side="left")
        self.pick_count = tk.Label(top, text="", anchor="e")
        self.pick_count.pack(side="right")
        cols = ("use", "replay", "time", "what", "who", "lists")
        self.tree = ttk.Treeview(f5, columns=cols, show="headings", height=9, selectmode="none")
        for c, t, w in (("use", "Use", 44), ("replay", "Replay", 56), ("time", "Time", 70), ("what", "What", 170),
                        ("who", "Player", 170), ("lists", "Playlist", 100)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w", stretch=(c in ("who", "lists")))
        sb = ttk.Scrollbar(f5, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8), pady=(0, 8))
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        self.tree.bind("<Button-1>", self.click_pick)
        self.items, self.sel = [], {}
        f4 = tk.Frame(self)
        f4.pack(fill="x", **pad)
        self.b_test = ttk.Button(f4, text="Test the first clip", command=lambda: self.go(True))
        self.b_test.pack(side="left")
        self.b_all = ttk.Button(f4, text="Make the highlight video", command=lambda: self.go(False))
        self.b_all.pack(side="left", padx=8)
        self.b_each = ttk.Button(f4, text="Make a file for every clip (for downloads)", command=lambda: self.go(False, True))
        self.b_each.pack(side="left")
        self.bar = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.bar.pack(fill="x", padx=12, pady=(6, 2))
        self.log = tk.Text(self, height=8, state="disabled", wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        threading.Thread(target=self.load_dates, daemon=True).start()
        self.after(150, self.pump)
        os.makedirs(DOCS, exist_ok=True)

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

    def load_angles(self):
        date = self.date.get().strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date) and date != getattr(self, "ang_date", None):
            self.ang_date = date
            threading.Thread(target=self.fetch_angles, args=(date,), daemon=True).start()
            threading.Thread(target=self.fetch_items, args=(date,), daemon=True).start()

    def fetch_angles(self, date):
        try:
            import highlights
            self.q.put(("angles", (date, highlights.fetch_sync(date)["angles"])))
        except Exception:
            self.q.put(("angles", (date, [])))

    def show_angles(self, date, angles):
        if date != self.date.get().strip():
            return
        for w in self.ang_rows.winfo_children():
            w.destroy()
        self.ang_files = {}
        angles = [a for a in angles if a["off"]]
        if not angles:
            self.ang_info.config(text="This game has no matched extra cameras. Goals will use the main camera only.")
            return
        self.ang_info.config(text="Choose each camera's video file and every goal is shown again from the camera behind "
                                  "the net the Kings scored on. Skip any you do not have.")
        for a in angles:
            row = tk.Frame(self.ang_rows)
            row.pack(fill="x", pady=2)
            lbl = tk.Label(row, text="No file chosen", anchor="w")
            ttk.Button(row, text="Choose %s video..." % a["name"], width=26,
                       command=lambda a=a, lbl=lbl: self.pick_angle(a["name"], lbl)).pack(side="left")
            lbl.pack(side="left", padx=8)
        if len(angles) > 1:
            row = tk.Frame(self.ang_rows)
            row.pack(fill="x", pady=(6, 2))
            tk.Label(row, text="In period 1 the Kings attack the end with:").pack(side="left")
            self.attack.set(angles[0]["name"])
            ttk.Combobox(row, textvariable=self.attack, values=[a["name"] for a in angles], width=16,
                         state="readonly").pack(side="left", padx=8)
        tk.Label(self.ang_rows, anchor="w", justify="left", wraplength=580,
                 text="Goals get one short replay from the camera behind the net they were scored on. "
                      "Use the Replay column in the list below to add one to any other clip.").pack(fill="x", pady=(4, 0))
        ttk.Checkbutton(self.ang_rows, text="Slow motion on replays (silent)", variable=self.slow).pack(anchor="w")
        zr = tk.Frame(self.ang_rows)
        zr.pack(fill="x", pady=(0, 6))
        tk.Label(zr, text="Zoom in on the replays:").pack(side="left")
        ttk.Combobox(zr, textvariable=self.zoom, values=["No zoom", "1.25x", "1.5x", "2x"], width=9,
                     state="readonly").pack(side="left", padx=8)

    def fetch_items(self, date):
        try:
            import highlights
            self.q.put(("items", (date, highlights.catalog(date))))
        except Exception as e:
            self.q.put(("items_err", str(e)))

    def show_items(self, date, items):
        if date != self.date.get().strip():
            return
        self.items = items
        self.sel = {i["id"]: {"use": bool(i["default"]), "replay": i["kind"] == "goal"} for i in items}
        lists = sorted({l for i in items for l in i["lists"]})
        self.flt_cb["values"] = ["Goals and highlights", "Everything", "Goals", "Saves", "Shots"] + ["Playlist: " + l for l in lists]
        self.draw_picks()

    def shown(self):
        f = self.flt.get()
        out = []
        for i in self.items:
            if f == "Everything":
                ok = True
            elif f == "Goals":
                ok = i["kind"] == "goal"
            elif f == "Saves":
                ok = i["kind"] == "save"
            elif f == "Shots":
                ok = "shot" in i["tag"].lower() or i["kind"] == "save"
            elif f.startswith("Playlist: "):
                ok = f[10:] in i["lists"]
            else:
                ok = i["default"] or self.sel.get(i["id"], {}).get("use")
            if ok:
                out.append(i)
        return out

    def draw_picks(self):
        import highlights
        self.tree.delete(*self.tree.get_children())
        roster = getattr(self, "roster", None)
        if roster is None:
            roster = self.roster = highlights.fetch_roster()
        for i in self.shown():
            s = self.sel[i["id"]]
            sec = int(i["sec"])
            who = ("#%s %s" % (i["num"], roster.get(str(i["num"]), ""))).strip() if i["num"] else ""
            what = i["tag"] + (" (" + i["label"] + ")" if i["kind"] == "clip" and i["label"] not in (i["tag"], "") and i["label"] != i["tag"] + (" #" + i["num"] if i["num"] else "") else "")
            self.tree.insert("", "end", iid=i["id"], values=("[x]" if s["use"] else "[ ]", "[x]" if s["replay"] else "[ ]",
                             "%d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60), what, who, ", ".join(i["lists"])))
        self.count_picks()

    def count_picks(self):
        n = sum(1 for s in self.sel.values() if s["use"])
        self.pick_count.config(text="%d picked" % n)

    def click_pick(self, e):
        row, col = self.tree.identify_row(e.y), self.tree.identify_column(e.x)
        if not row or col not in ("#1", "#2"):
            return
        key = "use" if col == "#1" else "replay"
        s = self.sel[row]
        s[key] = not s[key]
        if key == "replay" and s[key]:
            s["use"] = True
        self.tree.set(row, "use", "[x]" if s["use"] else "[ ]")
        self.tree.set(row, "replay", "[x]" if s["replay"] else "[ ]")
        self.count_picks()

    def tick_shown(self, on):
        for i in self.shown():
            self.sel[i["id"]]["use"] = on
        self.draw_picks()

    def pick_angle(self, name, lbl):
        p = filedialog.askopenfilename(title="Choose the %s video" % name,
                                       filetypes=[("Video", "*.mov *.mp4 *.mkv *.m4v *.avi"), ("All files", "*.*")])
        if p:
            self.ang_files[name] = p
            lbl.config(text=os.path.basename(p))

    def load_dates(self):
        try:
            import highlights
            self.q.put(("dates", highlights.game_dates()))
        except Exception as e:
            self.q.put(("dates_err", str(e)))

    def go(self, test, each=False):
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
        out = os.path.join(DOCS, "clips_" + date) if each else os.path.join(DOCS, "Kings_highlights_%s%s.mp4" % (date, "_test" if test else ""))
        angles = [{"name": n, "file": f} for n, f in self.ang_files.items()]
        picks = []
        for i in self.items:
            s = self.sel.get(i["id"])
            if s and s["use"]:
                picks.append(dict(i, replay=s["replay"]))
        if not each and not picks:
            messagebox.showinfo("Highlight video", "Tick at least one clip in the list first.", parent=self)
            return
        self.busy = True
        self.bar["value"] = 0
        self.b_test.config(state="disabled")
        self.b_all.config(state="disabled")
        self.b_each.config(state="disabled")
        keep_awake(True)
        threading.Thread(target=self.work, args=(date, off, test, out, each, angles, self.attack.get() or None,
                                                 self.slow.get(), self.zoom_value(), picks), daemon=True).start()

    def zoom_value(self):
        m = re.match(r"^([\d.]+)x$", self.zoom.get())
        return float(m.group(1)) if m else 1.0

    def work(self, date, off, test, out, each=False, angles=None, attack=None, slow=False, zoom=1.0, picks=None):
        try:
            import highlights
            kw = {} if each else {"angles": angles, "attack": attack, "slow": slow, "zoom": zoom, "picks": picks}
            (highlights.make_each if each else highlights.make_video)(self.video, date, out, off, test, None,
                                  log=lambda t: self.q.put(("line", t)),
                                  progress=lambda i, n: self.q.put(("bar", 100.0 * i / n)), **kw)
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
                elif kind == "items":
                    self.show_items(*val)
                elif kind == "items_err":
                    self.add_log("Could not load the clip list: " + val)
                elif kind == "angles":
                    self.show_angles(*val)
                elif kind == "dates":
                    self.cb["values"] = val
                    if val and not self.date.get():
                        self.date.set(val[0])
                    self.lbl_dates.config(text="Pick the game, or type a date.")
                    self.load_angles()
                elif kind == "dates_err":
                    self.lbl_dates.config(text="Could not load the list (no internet?). Type the date, like 2026-10-18.")
                elif kind in ("done", "fail"):
                    self.busy = False
                    keep_awake(False)
                    self.b_test.config(state="normal")
                    self.b_all.config(state="normal")
                    self.b_each.config(state="normal")
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
            messagebox.showerror("Kings Highlight Video", "The window could not start. Details were saved in error_log.txt.\n\n" + text[-600:])
        except Exception:
            pass

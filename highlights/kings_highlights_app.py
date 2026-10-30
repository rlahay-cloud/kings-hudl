"""Kings HUDL Highlight Video maker, its own small Windows program.

Cuts the Kings goals and Highlight clips that Kings HUDL has for a game out of the full game video
on this computer and joins them into one video. Nothing is uploaded. It is separate from the game analyzer.
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
    """Cuts the Kings goals and Highlight clips from Kings HUDL out of the game video and joins them."""

    def __init__(self):
        super().__init__()
        self.title("Kings Highlight Video")
        self.geometry("640x560")
        self.minsize(560, 480)
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
        self.video = None
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
        out = os.path.join(DOCS, "Kings_highlights_%s%s.mp4" % (date, "_test" if test else ""))
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
            messagebox.showerror("Kings Highlight Video", "The window could not start. Details were saved in error_log.txt.\n\n" + text[-600:])
        except Exception:
            pass

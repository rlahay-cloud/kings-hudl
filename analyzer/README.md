# Kings HUDL game analyzer (version 3)

This reads a wide panorama game video and gives you data to paste into Kings HUDL: faceoffs with zone and win percent, time on ice, goals, penalties and stoppages. It is a helper. You confirm a few things by tapping.

## How to run it

**On your Windows computer (recommended, no uploads, no Google):**

1. On GitHub, open the kings-hudl repository, click Code, then Download ZIP. Unzip it.
2. Open the `analyzer` folder, then `windows`. Double click `Install_Kings_Analyzer.bat` and wait for DONE (10 to 25 minutes, needs internet, first time only).
3. Double click the **Kings Analyzer** shortcut that appears on your desktop. Choose the game video, pick the 5 minute test, press Start, and note the minutes left it shows. Multiply by the game length to plan the full run.
4. The whole game can take a few hours with no graphics card. It keeps the computer awake, so leave it plugged in, overnight is fine. Results save in Documents\KingsAnalyzer and a stopped run carries on if you untick Start over.
5. When it finishes, the review page opens. Choose the same video there when it asks.

Details are in `windows/README_WINDOWS.txt`.

**In Google Colab (needs a Google sign in and an upload):** open the notebook [Kings_Analyzer in Colab](https://colab.research.google.com/github/rlahay-cloud/kings-hudl/blob/main/analyzer/Kings_Analyzer.ipynb), set the runtime to T4 GPU, drag the video in, and press Play on steps 1 to 4.

To test first in Colab, set END_SECONDS to 300 in step 3.

## The review app (review.html)

Open `review.html` in Chrome (the Windows app does this for you), then choose the game video (it stays on your computer). The video sits beside a timeline that shows activity, stoppages, line changes, faceoffs, period starts and shots. Click the timeline to jump. Space plays and pauses, arrows move 1 second, Shift and arrows move 5 seconds.

Tabs on the right:

- **Roster:** tick which colour groups are the Kings, add names and extra numbers, set a time offset.
- **Periods:** say which way the Kings attack in each period.
- **Line changes (N left):** a queue. Each card has pictures from the bench. Tap who came off and who came on. Names carry forward. Next to check jumps to the next one.
- **Stoppages:** found from the scoreboard clock. Delete wrong ones or add your own.
- **Faceoffs:** spot and zone are automatic. Tap Win or Loss. Win percent by zone, and lines for Kings HUDL.
- **Shots:** not automatic. Press S or D at a shot. Lines for Kings HUDL.
- **Penalties:** scoreboard hints to check, plus your own marks.
- **Shifts:** ice time per player (game time, stoppages removed) from either the tracks you ticked or the line changes you confirmed. Copy lines for the Shifts tab.
- **Heatmaps:** a rink diagram with a heat map and path for one player (whole video or one shift) or the whole team, live play only if you like. Below it, "Which tracks are this player?" with pictures. Tick the tracks that show the player. The more you tick, the more the app labels for you, and it shows what percent of ice time is labelled with confidence.

Everything saves in the browser as you go. Save review file and Load review file keep a copy. Export JSON and Export shifts CSV are at the top. `review_classic.html` is the older page.

## Paste into Kings HUDL

- **Faceoffs, goals, penalties:** Coach's Corner, Game analysis, pick the game, "Add goals and penalties from the game analyzer". Paste, tap Add these lines, check them, tap Share to Kings HUDL.
- **Shifts:** Coach's Corner, Shifts, "Add shifts from the game analyzer". Paste, tap Add these lines, tap Save for everyone.

Times are in video seconds. If your video starts at a different moment than the main stream, type the difference into the offset box on the page first.

## What it can and cannot do (honest list)

- **Players are matched by look, which is only a hint.** In a test on your clip, a skater's second half was matched to their first half correctly about 1 time in 3 when the program had to choose among about 10 look-alikes (chance would be about 1 in 10). So expect to answer a fair number of questions. Position and timing rules (a player cannot be in two places, tracks that follow on from each other) help, and the review page reports how much is labelled with confidence so you can see how it is doing.
- **Numbers are a hint, not an answer.** Only skaters seen big and close have readable numbers, and reads are often wrong. The program never fills a number in for you.
- **Faceoff spot and zone are automatic.** Win or Loss is a tap, because the video cannot show who won the puck. Spots were checked on the first 60 seconds of your clip (centre ice came out right). Other zones are untested on a real game, so look at the flags.
- **Line changes are suggestions.** They come from skaters appearing at or leaving the bench boards. A busy bench can merge two changes into one card.
- **Shots are not found.** The puck is too small to find reliably.
- **Goals and penalties** depend on the scoreboard. The score change finder had no false alarms on a quiet 2 minutes, but was never tested on a real goal or penalty. Every line says CHECK.
- **One rink is set up:** Ingredion Centre Rink 1, with its ice outline, scoreboard and blue lines in `rinks/ingredion_rink1.json`.
- **Speed:** it reads the video once, in order. How long a full game takes on the free T4 card is not known yet. Do the 5 minute test first and multiply by the game length. On a computer with no graphics card it was about 20 seconds of work for each second of video, so use Colab.

## Hudl's data points we follow

Hudl hockey tracks time on ice, faceoffs and win percent by zone, goals, power plays, and tags tied to video. This tool covers time on ice, faceoffs by zone, goals and penalties. Zone entries, dump ins and Instat style stats need a puck tracker, which is not built.

## Files in an analysis folder

- `scoreboard.jsonl` what the scoreboard showed each second
- `detections.jsonl` skaters on the ice each second (skipped when the clock sits still a long time)
- `bench.jsonl` tiny pictures of skaters near the bench
- `meta.json`, `analysis.json`, `review.html`

Command line, if you ever want it: `python kings_analyzer.py analyze VIDEO OUTDIR`

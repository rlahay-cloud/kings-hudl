# Kings HUDL game analyzer (version 2)

This reads a wide panorama game video and gives you data to paste into Kings HUDL: faceoffs with zone and win percent, time on ice, goals, penalties and stoppages. It is a helper. You confirm a few things by tapping.

## How to run it (no Claude needed)

1. Open the notebook: [Kings_Analyzer in Colab](https://colab.research.google.com/github/rlahay-cloud/kings-hudl/blob/main/analyzer/Kings_Analyzer.ipynb). Use Chrome.
2. Click Runtime, Change runtime type, pick T4 GPU, Save.
3. Click the folder icon on the left and drag your game video in. Wait for the upload to finish.
4. Press Play on steps 1, 2, 3, 4 in order. Step 4 does the whole game in one go and downloads `review.html`.
5. Open `review.html` on your computer and work down the page.
6. Paste the results into Kings HUDL (below).

To test first, set START 0 and END 300 in step 3. That does 5 minutes.

## What the review page gives you

- **Step 1 Colours:** tap the groups that are the Kings.
- **Step 5 Faceoffs:** one row per clock restart, with the spot, the zone (OZ, NZ, DZ) and a check flag if few skaters were seen. Say which way the Kings attack in each period. Tap Win, Loss or Skip, and type the centre's number if you like. It shows win percent by zone.
- **Step 6 Line changes:** one card per moment Kings skaters hit the bench, with small pictures. Type the numbers who came off and came on. The page carries the "on the ice now" list forward. It writes the shift lines and a time on ice table.
- **Step 4 Scoreboard events:** goals and penalties found from the scoreboard changing, as lines to check.
- **Steps 2 and 3** (naming every box) are still there as a fallback.

## Paste into Kings HUDL

- **Faceoffs, goals, penalties:** Coach's Corner, Game analysis, pick the game, "Add goals and penalties from the game analyzer". Paste, tap Add these lines, check them, tap Share to Kings HUDL.
- **Shifts:** Coach's Corner, Shifts, "Add shifts from the game analyzer". Paste, tap Add these lines, tap Save for everyone.

Times are in video seconds. If your video starts at a different moment than the main stream, type the difference into the offset box on the page first.

## What it can and cannot do (honest list)

- **Player numbers are not read automatically.** From this camera distance the numbers are too small and blurry (about 1 in 6 right in a test). You type them, but only at line changes (1 or 2 taps) instead of for every box.
- **Faceoff spot and zone are automatic.** Win or Loss is a tap, because the video cannot show who won the puck. Spots were checked on the first 60 seconds of your clip (centre ice came out right). Other zones are untested on a real game, so look at the flags.
- **Line changes are suggestions.** They come from skaters appearing at or leaving the bench boards. A busy bench can merge two changes into one card.
- **Shots are not found.** The puck is too small to find reliably.
- **Goals and penalties** depend on the scoreboard. The score change finder had no false alarms on a quiet 2 minutes, but was never tested on a real goal or penalty. Every line says CHECK.
- **One rink is set up:** Ingredion Centre Rink 1, with its ice outline, scoreboard and blue lines in `rinks/ingredion_rink1.json`.
- **Speed:** it reads the video once, in order. On the free T4 card a full game should take roughly 20 to 40 minutes, but this has not been timed on Colab yet. On a computer with no graphics card it is about 10 seconds of work for each second of video, so use Colab.

## Hudl's data points we follow

Hudl hockey tracks time on ice, faceoffs and win percent by zone, goals, power plays, and tags tied to video. This tool covers time on ice, faceoffs by zone, goals and penalties. Zone entries, dump ins and Instat style stats need a puck tracker, which is not built.

## Files in an analysis folder

- `scoreboard.jsonl` what the scoreboard showed each second
- `detections.jsonl` skaters on the ice each second (skipped when the clock sits still a long time)
- `bench.jsonl` tiny pictures of skaters near the bench
- `meta.json`, `analysis.json`, `review.html`

Command line, if you ever want it: `python kings_analyzer.py analyze VIDEO OUTDIR`

# Kings HUDL game analyzer (version 3)

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

1. **Colours:** tap the groups that are the Kings.
2. **Name each player once:** the program groups skaters by how they look across the game and shows about 20 player cards. Type the jersey number on each card. Use "Not Kings" for referees and the other team.
3. **Check only what it is unsure about:** it labels everything else from your answers, shows how much ice time is labelled with confidence, and lists the least certain pieces first, with its best guesses as one tap buttons. Answer as many as you like. If a skater was big and close, it also shows a number it read, as a hint.
4. **Ice time, shifts, paths and heat maps:** time on ice and shifts per player (clock time, with stoppages taken out), a path and heat map for each shift or the whole game, and a team heat map. It writes shift lines for the Shifts tab and a tracking file.
5. **Faceoffs with zone:** tap Win or Loss. Zone and spot are automatic.
6. **Line changes:** bench pictures to confirm who came on and off, if you prefer that way.

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

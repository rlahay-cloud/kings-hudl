# Kings HUDL game analyzer (version 1)

This finds the skaters in a wide panorama video, follows them, and helps you make shifts without tapping every line change by hand. It is a helper, not a robot coach. A person still names each box once.

## What it does

1. **Finds skaters.** It looks at the video a couple of times a second and draws a box around every person standing on the ice. Bench, crowd and walkway are ignored because only the ice outline counts.
2. **Sorts by jersey colour.** It guesses which boxes are blue, white or dark (referee, goalie gear). You tell it which groups are the Kings.
3. **Follows each box.** A box seen in picture after picture becomes a "track", one stretch of one player on the ice.
4. **Reads the real scoreboard** (Ingredion Centre Rink 1 only for now). From the clock it gets exact stoppages (the clock stops) and where each period starts. It watches the score boxes and the penalty boxes and flags when they change.
5. **Tries to read jersey numbers.** The guess only shows as a small hint under the box, labelled as often wrong. It never fills a number in for you.
6. **Makes a review page.** `review.html` shows a small picture for every track. You pick your team colours, type each jersey number once, and the page writes the shifts lines. A second part lists goals and penalty box events from the scoreboard, as lines for Game analysis.

## What it cannot do yet

- **Jersey numbers are weak.** In a test on your clip the reader got about 1 in 6 right, and sometimes guessed a wrong number even when several pictures agreed. The camera is far away and numbers are small, angled and blurry. You will type most numbers. A better fix is to learn each player from the boxes you name, which would be a later version.
- **Shots are not found.** The puck is visible when it is close, but a simple finder picks up hundreds of false dots on lines and ice marks. A real puck finder needs hundreds of labelled pictures first.
- **Goals and penalties come from the scoreboard changing.** That depends on the scoreboard being kept up to date and in the picture. The score change finder was tested on a quiet 2 minutes (no false alarms) but never on a real goal. The penalty boxes were blank in the test clip, so that part is untested on a real penalty. Every line it writes says CHECK, and you should watch each one.
- **Only one rink is set up.** The ice outline and scoreboard positions are for Ingredion Centre Rink 1. Another rink needs its own file in `rinks/`.
- **A player who skates behind another player may split into two boxes.** Type the same number on both and they merge.

## How to run it

Use the Colab notebook `Kings_Analyzer.ipynb` ([open it in Colab](https://colab.research.google.com/github/rlahay-cloud/kings-hudl/blob/main/analyzer/Kings_Analyzer.ipynb)) (a free Google graphics card makes a game take about an hour). Open the notebook, drag the game video into the Files panel on the left, press the Play buttons from top to bottom, then open the `review.html` it downloads. Google Drive is optional.

On a computer without a graphics card the same steps work but take many hours. Command line version:

```
python kings_analyzer.py detect VIDEO OUTDIR --rink rinks/ingredion_rink1.json
python kings_analyzer.py build  VIDEO OUTDIR --rink rinks/ingredion_rink1.json
```

## Other rinks

The ice outline lives in `rinks/`. To add a rink, copy `ingredion_rink1.json`, change the name and the corner points (in pixels of the full video, starting at the bottom left and going around the far boards). Ask Claude to draw it from a picture of the rink.

## Putting the shifts on the site

**Shifts:** open Coach's Corner, then Shifts, pick the game, scroll down to **Add shifts from the game analyzer**, paste the lines and tap **Add these lines**. Then tap **Save for everyone**. Undo last tap takes the whole paste back.

**Goals and penalties:** open Coach's Corner, then Game analysis, pick the game, scroll down to **Add goals and penalties from the game analyzer**, paste the lines and tap **Add these lines**. They show in the Events list. Tap each time to watch it, fix or delete wrong ones, then tap **Share to Kings HUDL**. Times are in seconds of the video you analyzed. If that video starts at a different moment than the main stream, type the difference into the page before copying.

## Files in an analysis folder

- `detections.jsonl` one line per picture, saved as it goes (this is what lets a stopped run carry on)
- `meta.json` details about the video
- `scoreboard.jsonl` one line per second of what the scoreboard showed
- `analysis.json` the tracks, the scoreboard results and stoppages
- `review.html` the page you open

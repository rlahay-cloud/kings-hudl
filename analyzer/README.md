# Kings HUDL game analyzer (version 1)

This finds the skaters in a wide panorama video, follows them, and helps you make shifts without tapping every line change by hand. It is a helper, not a robot coach. A person still names each box once.

## What it does

1. **Finds skaters.** It looks at the video a couple of times a second and draws a box around every person standing on the ice. Bench, crowd and walkway are ignored because only the ice outline counts.
2. **Sorts by jersey colour.** It guesses which boxes are blue, white or dark (referee, goalie gear).
3. **Follows each box.** A box that is seen in picture after picture becomes a "track", which is one stretch of one player on the ice.
4. **Makes a review page.** `review.html` shows a small picture for every track. You pick your team's colour, type the jersey number once per box, and the page writes the shifts lines.
5. **Suggests stoppages.** When nobody is moving for a few seconds it suggests a stop and a go, so the stop time does not count as ice time.

## What it cannot do yet

- It cannot read jersey numbers by itself. Players far from the camera are too small. You type them.
- It does not find shots, goals or penalties yet.
- A player who skates behind another player may split into two boxes. Type the same number on both and they merge.
- Stoppages are a guess. Check them on the site before you save.

## How to run it

Use the Colab notebook `Kings_Analyzer.ipynb` ([open it in Colab](https://colab.research.google.com/github/rlahay-cloud/kings-hudl/blob/main/analyzer/Kings_Analyzer.ipynb)) (a free Google graphics card makes a game take about an hour). Put the game in Google Drive in a folder called `KingsHUDL games`, press the Play buttons from top to bottom, then open `review.html` from your Drive.

On a computer without a graphics card the same steps work but take many hours. Command line version:

```
python kings_analyzer.py detect VIDEO OUTDIR --rink rinks/ingredion_rink1.json
python kings_analyzer.py build  VIDEO OUTDIR --rink rinks/ingredion_rink1.json
```

## Other rinks

The ice outline lives in `rinks/`. To add a rink, copy `ingredion_rink1.json`, change the name and the corner points (in pixels of the full video, starting at the bottom left and going around the far boards). Ask Claude to draw it from a picture of the rink.

## Putting the shifts on the site

Open Coach's Corner, then Shifts, pick the game, scroll down to **Add shifts from the game analyzer**, paste the lines and tap **Add these lines**. Then tap **Save for everyone**. Undo last tap takes the whole paste back. Times are in seconds of the video you analyzed. If that video starts at a different moment than the main stream, type the difference into the page before copying.

## Files in an analysis folder

- `detections.jsonl` one line per picture, saved as it goes (this is what lets a stopped run carry on)
- `meta.json` details about the video
- `analysis.json` the tracks and stoppage suggestions
- `review.html` the page you open

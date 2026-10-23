# Kings HUDL

A season stats website for the team, called Kings HUDL. Open it on a phone or computer to see the record, leaders, player cards, game box scores, goalies and video moments.

## Coaches

Coaches open **Coaches corner**, type their name and the coach passcode once, load the game video, and tap the buttons (Goal, Save, Chance, Good play, Breakout, Blocked shot, Review). Share to Kings HUDL sends their file into the games folder, one file per coach. The Highlights tab (view only) shows everyone's highlights together and can filter by coach and type. Setup for the sending helper is in `worker/SETUP.md`.

## After each game

1. In Streamn, press End Game. Streamn writes files into its output folder.
2. Open the **games** folder in this repository on GitHub, choose Add file, then Upload files.
3. Drag in the dated file named like `game_summary_2026-10-24_193000.txt`. Do not use the plain `game_summary.txt`, it has no date.
4. Choose Commit changes. The site updates in about a minute.

The site finds every file in the games folder by itself. No list to edit.

## Video moments (optional)

1. Copy Streamn's `timestamps.txt` and rename the copy to `timestamps_2026-10-24.txt` (use the game date). Upload it to the games folder.
2. Open `videos.txt` here and add a line: `2026-10-24 https://youtu.be/yourvideo`

Goals and penalties then become links that jump to that moment in the YouTube video.

## Player photos

Put one photo per player in the **photos** folder, named by jersey number: `4.jpg`, `10.jpg` (`.png` and `.webp` also work). They show on player cards and player pages. Anyone with the site link can see them, so get permission first.

## Highlights

Open **Coaches corner**, pick the game, load the YouTube link (or open a video file from the device), and tap **Highlight** whenever something happens. Label it, tag it and add player numbers afterwards. Then Save file and upload it to the games folder as `clips_2026-10-24.txt`. The site does not store video.

## Shot map

Open **Coaches corner**, then **Mark shots**. Tap where the shot was taken, pick the player, then tap Goal or Saved. Mark every shot as if attacking the net on the right. Save the file and upload it as `shots_2026-10-24.txt`. The Shot map tab then shows dots and heat by game, player and result.

## Video tab

The Video tab collects every clip from every game: coach highlights plus Streamn's goals and penalties (from the timestamps files). Filter by game, type, who marked it, or player. Tap a time to watch it. A game needs its YouTube link in `videos.txt`.

## Roster from Streamn

After End Game, Streamn writes `season_backup.txt`. Upload it to the top of this repository (replace the old one). Kings HUDL then uses Streamn's roster, with names, for the shot marking buttons, player lists and goalie names. `roster.json` is only used for names Streamn does not have.

## Names

Player names come from `roster.json`. Edit it to add or fix names. Goalies can go in a `goalies` list with the same `n` and `name` fields.

## Notes

- Stats are added up from the game files, so the season only counts games that were uploaded.
- The summary lists every goal with the period, time, who scored and who assisted, so the game page shows a goals list. Streamn keeps the last 16 goals of a game.
- Two games on the same date share one video link and one timestamps file.
- Add `?sample` to the site address to preview it with made up data.

## Game events (no name)

In Coaches corner, the Game events tab marks basic moments: Goal, Goal against, Penalty and Away Penalty. Goals take a scorer and up to two assists, penalties take the player. These are saved with no coach name and show in the Video tab under "Game events". The passcode is still needed so strangers cannot write to the repo.

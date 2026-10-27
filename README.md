# Kings HUDL

A season stats website for the team, called Kings HUDL. Open it on a phone or computer to see the record, leaders, player tables, game box scores, goalies and video moments.

## Coaches

Coaches open **Coach’s Corner**, type their name and the coach passcode once, load the game video, and tap the buttons (Goal, Save, Chance, Good play, Breakout, Blocked shot, Review). Share to Kings HUDL sends their file into the games folder, one file per coach. The Video tab shows everyone's clips together and can filter by game, coach, type, player and playlist. Setup for the sending helper is in `worker/SETUP.md`.

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

Put one photo per player in the **photos** folder, named by jersey number: `4.jpg`, `10.jpg` (`.png` and `.webp` also work). They show on player pages. Anyone with the site link can see them, so get permission first.

## Highlights

Open **Coach’s Corner**, pick the game, load the YouTube link (or open a video file from the device), and tap **Highlight** whenever something happens. Label it, tag it and add player numbers afterwards. Then Save file and upload it to the games folder as `clips_2026-10-24.txt`. The site does not store video.

## Shot map

Open **Coach’s Corner**, then **Mark shots**. Tap where the shot was taken, pick the player, then tap Goal or Saved. Mark every shot as if attacking the net on the right. Save the file and upload it as `shots_2026-10-24.txt`. The Shot map tab then shows dots and heat by game, player and result. Under the map, a Shot zones table splits the rink into slot, left circle, right circle, behind the net, point and mid range, and long range, with shots, shots on goal, goals and shooting % for each team, plus slot shots and average shot distance. A rink picture shows each zone in its real shape: the slot is a wedge in front of the net (within 25 ft, 40 degrees either side of straight on), then the left circle and right circle (seen from the shooter, facing the net), a point and mid range ring (25 to 50 ft), behind the net, and long range. Circles over each zone grow with the number of shots and change colour with shooting % (blue low, pink 40% or more). A Situation filter shows even strength, power play or penalty kill shots (only shots marked in Game analysis have a time, and a penalty needs an end time marked to count as power play).

## Video tab

The Video tab collects every clip from every game: coach highlights plus Streamn's goals and penalties (from the timestamps files). Each clip is listed at the time it was marked, and plays from 8 seconds before that time to 2 seconds after it. Every goal and penalty is added to a playlist called Highlights automatically. Filter by game, type, who marked it, or player. Tap a time to watch it. A game needs its YouTube link in `videos.txt`.

## Roster from Streamn

After End Game, Streamn writes `season_backup.txt`. Upload it to the top of this repository (replace the old one). Kings HUDL then uses Streamn's roster, with names, for the shot marking buttons, player lists and goalie names. `roster.json` is only used for names Streamn does not have.

## Names

Player names come from `roster.json`. Edit it to add or fix names. Goalies can go in a `goalies` list with the same `n` and `name` fields.

## Notes

- Stats are added up from the game files, so the season only counts games that were uploaded.
- The summary lists every goal with the period, time, who scored and who assisted, so the game page shows a goals list. Streamn keeps the last 16 goals of a game.
- Two games on the same date share one video link and one timestamps file.
- Add `?sample` to the site address to preview it with made up data.

## Coach’s Corner

Coach’s Corner opens on **Clips**: a list of every clip that already exists, with filters for game, type, playlist and "only clips with drawings". Tap a clip and it opens in the clip editor.

In the editor the coach pauses the video, taps **Draw on this frame**, and uses the pen, arrow, line, circle or text tools in six colours to explain the play. Each drawing keeps its own hold time (2 to 12 seconds). **Save drawings for everyone** sends them to the games folder as `draw_DATE_STARTSECOND.txt`. When anyone plays that clip in the Video tab, the video pauses at the drawing, shows it for the hold time, then carries on. Drawings belong to a clip by game date and start second, so changing a clip's start time detaches them.

The other sections hold the marking tools: **Game analysis** (review, below), **Shot marker** and **Players** (names and positions).

## Shifts (ice time)

Open **Coach’s Corner**, then **Shifts**, pick the game and play the video. Tap **Start tracking** when play starts and **Stop tracking** at every stoppage. Time only counts while tracking is on, measured on the video timeline, so line changes during a stoppage cost nothing. Tap a player's number when he steps on the ice and tap it again when he comes off. Players can be toggled at any time, including while tracking is stopped. **Everyone off** and **End of period** (clears the ice and stops tracking) clear the ice in one tap, and **Undo last tap** takes back the last tap. The shifts table builds as you tap, and a player still on the ice shows a running shift. Tap a player in the table to see each shift, and delete a shift (tap Delete twice) to remove it and its stat. When you reopen a game, the video starts at the last tracked time and the ice and tracking state are restored, and **Go to last tracked** jumps back there at any time. Deleting only changes the shared file once you tap Save for everyone. On a player page, each game in the Ice time table opens a dropdown of its shifts, and every shift has a watch link that plays the video from 4 seconds before the shift started until 2 seconds after the shift ended, so the whole shift plays. Each coach's shifts save to their own file (`shifts_DATE_name.txt`, or `shifts_DATE.txt` when no name is set), so coaches never overwrite each other. The Shifts tab, game page and player pages combine everyone's taps, show which coach tapped what, and only let you delete your own. The Shifts tab checks for other coaches' saves every 30 seconds, and the Refresh other coaches button checks right away. A save takes about a minute to appear because the site has to republish.

Save for everyone writes `shifts_DATE.txt` into the games folder (one line per tap: video second, on, off, stop or go). The game page then shows an Ice time table (shifts, total ice time, average, longest and shortest shift) and each player page shows ice time per game, shifts per game, average shift and longest shift.

## Coach’s Corner (game review)

One screen, Review, holds everything for coaches.

- **Full rink.** Tap the rink to choose a spot and a zone (our zone, neutral, their zone). The chosen zone is tinted. Shot counters for us and them sit above the rink and at each net. Filters turn the markers on or off, by team and by goal or shot.
- **What happened.** Shot (Goal, Shot on goal, Missed, Blocked) for us or them, Penalty on us or them, Zone entry, Zone exit, Faceoff (tap the rink for the zone, then Win or Loss) and Special teams. Goal is in one place only.
- **Video and timeline.** Load the game video. Every mark shows on a timeline. Tap the timeline to jump, or tap a mark to select it and add players. A goal takes a scorer and up to two assists.
- **Coach notes.** Good play, Breakout, Chance and Review save with the coach's name and show in the Video tab.
- **No names on game facts.** Shots, goals, penalties and the rest of the review save as one shared file per game, `games/review_DATE_game.txt`. Goals and penalties also show in the Video tab and on player pages.

Share to Kings HUDL sends everything at once. Player pages show goals, assists and penalties by default, with buttons to switch on the rest. If two coaches review the same game, whoever shares last replaces the shared review file, so load the game first and add to what is there.

## Upcoming games

The Overview page shows the next two games from `schedule.txt` in the main folder. Each line is `date|start time|opponent|H or A|arena`. Add a line for each new game. Games drop off the page by themselves two hours after they start.

## Game setup: period times and extra camera angles

Open **Coach’s Corner**, then **Game setup**, and pick the game. Tap **+ New game** to make one that is not in the site yet: type the date, opponent, home or away, start time, arena and the YouTube link, or fill them from the schedule. The same details can be edited later on any game. Play the main video and tap **Starts now** at each puck drop and **Ends now** at each horn. After that, times on clips, goals, penalties and shifts also show period time, like P2 4:12 (real time since the period began, stoppages included). Between periods it says Intermission. Nothing already saved is changed: every time is still stored in main video seconds, and the setup file only translates them. Games with no setup look exactly as before.

To add another camera, paste its YouTube link under **Extra camera angles**, tap **Match**, pause the main video and the angle on the same moment (a puck drop works well), and tap **Match**. Clips then show a camera picker, and the angle opens at the matching moment. Setup is saved as `games/sync_DATE.txt` and needs the helper updated (paste `worker/worker.js` into Cloudflare again).

Games that have no Streamn file still show up: once a played game has review marks in Game analysis, the site makes the game itself (opponent from Game setup, then the schedule). Its score, shots, faceoffs, plus/minus and players come from the marks. Until a goal is marked it is listed as not scored yet and is left out of the record and player stats, so a half-marked game does not show as a tie.

## Game analyzer (version 1, early)

The `analyzer` folder holds a helper that watches a wide panorama game video, finds and follows the skaters, and makes a review page where you type each jersey number once. It then writes shifts lines you paste into Coach’s Corner, Shifts, under **Add shifts from the game analyzer**. It runs on a free Google Colab graphics card, not on your computer, and it cannot read jersey numbers or find shots yet. See `analyzer/README.md`.

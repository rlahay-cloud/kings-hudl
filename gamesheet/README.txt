KINGS FILM ROOM GAMESHEET UPDATER (Windows)

What it does
Double click Update_GameSheet.bat. A browser window opens by itself and visits the
division standings, then each team page. It clicks every Export button, saves the
files into the "exports" folder, and sends the division standings to Kings Film Room.
Leave the window alone while it works.

On a Mac
Double click Update_GameSheet.command instead. The first time, macOS may say it cannot
be opened: right click it, choose Open, then Open again. Python 3 from python.org is needed.

First time
1. Install Python from python.org if you do not have it. Tick "Add Python to PATH".
2. Double click Update_GameSheet.bat. The first run installs what it needs.
3. When asked, type your Kings Film Room coach passcode. It is remembered on this computer only.

Important to know
This is a first version. It was written without being able to open GameSheet, so the
buttons on the team pages may need adjusting. If anything says "no Export button
found" or a team is skipped, zip the "debug" folder and "last_run.txt" and send them
to Claude. Claude will fix it and send you a new version.

Right now only the division standings go to the Film Room. The team files are saved
in the exports folder until we decide what each one should show on the site.

#!/bin/bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/ then run this again."
  read -p "Press Enter to close"
  exit 1
fi
if [ ! -f .ready ]; then
  echo "First time setup. This takes a few minutes and only happens once."
  python3 -m pip install --upgrade playwright
  python3 -m playwright install chromium
  echo done > .ready
fi
python3 update_gamesheet.py
echo
echo "All finished. You can close this window."
read -p "Press Enter to close"

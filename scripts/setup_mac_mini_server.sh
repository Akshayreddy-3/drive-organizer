#!/bin/bash
# setup_mac_mini_server.sh — run ONCE on the Mac mini that will serve the model to your other PCs.
# Needs no administrator password and no Homebrew. See SERVER_SETUP.md ("A Mac mini as the server").
#
#   bash scripts/setup_mac_mini_server.sh                    # install (listens on the Tailscale address only)
#   bash scripts/setup_mac_mini_server.sh --dry-run          # show what it would do, change nothing
#   bash scripts/setup_mac_mini_server.sh --remove           # stop and remove it again
#   bash scripts/setup_mac_mini_server.sh --all-interfaces   # listen on 0.0.0.0 (home Wi-Fi/LAN can reach it too)
#   bash scripts/setup_mac_mini_server.sh --model=qwen3:4b   # another model
#
# What it sets up: a per-user background service (LaunchAgent) that runs `ollama serve`
#   - listening only on this Mac's Tailscale address, so nothing on your home network can reach it
#     (if Tailscale isn't up yet it fails and retries, it never falls back to listening everywhere)
#   - keeping the model loaded (OLLAMA_KEEP_ALIVE=-1), one request at a time
#   - holding the Mac awake while it runs (caffeinate)
# It starts when you log in to the mini, not at power-on: after a restart, log in once.
set -euo pipefail

LABEL="com.driveorganizer.ollama"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/DriveOrganizerOllama.log"
PORT=11434
MODEL="qwen3:4b"
BIND="tailscale"
DRY=0
REMOVE=0

for arg in "$@"; do
  case "$arg" in
    --dry-run)         DRY=1 ;;
    --remove)          REMOVE=1 ;;
    --all-interfaces)  BIND="all" ;;
    --model=*)         MODEL="${arg#--model=}" ;;
    -h|--help)         sed -n '2,17p' "$0"; exit 0 ;;
    *)                 echo "Unknown option: $arg (try --help)"; exit 2 ;;
  esac
done

fail() { echo "❌ $*"; exit 1; }
note() { if [ "$DRY" = 1 ]; then echo "[dry run] $*"; else echo "$*"; fi; }

[ "$(uname)" = "Darwin" ] || fail "This script is for the Mac mini (macOS)."
UID_NUM="$(id -u)"

# ── Remove ──
if [ "$REMOVE" = 1 ]; then
  if [ "$DRY" = 1 ]; then note "would stop $LABEL and delete $PLIST"; exit 0; fi
  launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "✅ Removed. The Ollama app on this Mac is untouched."
  exit 0
fi

# ── Find Ollama and Tailscale ──
OLLAMA=""
for p in /usr/local/bin/ollama /Applications/Ollama.app/Contents/Resources/ollama "$HOME/Applications/Ollama.app/Contents/Resources/ollama"; do
  if [ -x "$p" ]; then OLLAMA="$p"; break; fi
done
[ -n "$OLLAMA" ] || fail "Ollama isn't installed here. Install it from https://ollama.com, open it once, then run this again."

TS=""
for p in "$(command -v tailscale 2>/dev/null || true)" /Applications/Tailscale.app/Contents/MacOS/Tailscale; do
  if [ -n "$p" ] && [ -x "$p" ]; then TS="$p"; break; fi
done
TS_IP=""
if [ -n "$TS" ]; then TS_IP="$("$TS" ip -4 2>/dev/null | head -n 1 || true)"; fi

if [ "$BIND" = "all" ]; then
  HOST="0.0.0.0"
else
  HOST="$TS_IP"
  if [ -z "$HOST" ]; then
    if [ "$DRY" = 1 ]; then
      HOST="100.64.0.1"; note "Tailscale isn't set up on this Mac, so an example address ($HOST) is used below."
    elif [ -z "$TS" ]; then
      fail "Tailscale isn't installed here. Install it from https://tailscale.com/download, sign in, then run this again."
    else
      fail "Tailscale is installed but not connected. Open it, sign in, then run this again."
    fi
  fi
  case "$HOST" in 100.*) ;; *) fail "Unexpected Tailscale address '$HOST'." ;; esac
fi
LOCAL="$HOST"; [ "$HOST" = "0.0.0.0" ] && LOCAL="127.0.0.1"

# ── Make sure the port is free (the Ollama menu bar app runs its own server on it) ──
[ "$DRY" = 1 ] || { launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true; sleep 1; }
if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  MSG="Something is already listening on port $PORT — usually the Ollama menu bar app. Quit it (menu bar icon → Quit Ollama) and remove it from System Settings → General → Login Items, then run this again."
  if [ "$DRY" = 1 ]; then note "⚠️  $MSG"; else fail "$MSG"; fi
fi

# ── The background service ──
if [ "$DRY" = 1 ]; then TARGET="$(mktemp -t ollama-agent).plist"; else TARGET="$PLIST"; mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"; fi
cat > "$TARGET" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/caffeinate</string><string>-is</string>
    <string>$OLLAMA</string><string>serve</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>OLLAMA_HOST</key><string>$HOST:$PORT</string>
    <key>OLLAMA_KEEP_ALIVE</key><string>-1</string>
    <key>OLLAMA_NUM_PARALLEL</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>15</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST_EOF
plutil -lint "$TARGET" >/dev/null || fail "The service file it wrote is invalid (this is a bug)."

if [ "$DRY" = 1 ]; then
  echo; note "would write $PLIST:"; cat "$TARGET"; rm -f "$TARGET"
  note "would start it, wait for http://$LOCAL:$PORT, and download $MODEL if it is missing"
  exit 0
fi

echo "== Starting the model server on $HOST:$PORT"
launchctl bootstrap "gui/$UID_NUM" "$PLIST" || fail "macOS wouldn't start it. See $LOG"
UP=0
for _ in $(seq 1 40); do
  if curl -sf -m 2 "http://$LOCAL:$PORT/api/tags" >/dev/null 2>&1; then UP=1; break; fi
  sleep 1
done
[ "$UP" = 1 ] || fail "The server didn't come up. Look at $LOG (last lines: $(tail -n 3 "$LOG" 2>/dev/null | tr '\n' ' '))"

SEEN="$(lsof -nP -iTCP:$PORT -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print $9; exit}')"
echo "   listening on: ${SEEN:-unknown}"
if [ "$BIND" = "tailscale" ] && [ "$SEEN" != "$HOST:$PORT" ]; then
  launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
  fail "It is listening on '$SEEN', not on the Tailscale address only. Stopped it; nothing is exposed."
fi

if curl -sf -m 5 "http://$LOCAL:$PORT/api/tags" | grep -q "\"$MODEL\""; then
  echo "== Model $MODEL is already downloaded"
else
  echo "== Downloading $MODEL (a few GB)"
  OLLAMA_HOST="$LOCAL:$PORT" "$OLLAMA" pull "$MODEL"
fi

URL_HOST="${TS_IP:-$HOST}"
echo
echo "✅ Done. The Mac mini is serving $MODEL."
echo "   On each PC, put this line in the project's .env:"
echo "      OLLAMA_URL=http://$URL_HOST:$PORT"
echo "   (or the mini's Tailscale name instead of the number, if MagicDNS is on)"
echo "⚠️  Keep the mini logged in and plugged in. It starts at login, not at power-on."
echo "⚠️  Never forward port $PORT on your router — Ollama has no password. Tailscale is the only way in."

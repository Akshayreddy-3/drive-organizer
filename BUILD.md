# The packaged app (no Python, no Terminal)

The packaged app has Python and every library inside it. People install it like any other
app and open it with a double-click. It runs in the background and shows its page in the
browser; opening it again brings the page back, and Settings has a Quit button.

| | File to share | How people install it |
|---|---|---|
| Mac (Apple silicon) | `Drive-Organizer-Mac.dmg` | Open it, drag Drive Organizer onto Applications |
| Windows | `Drive-Organizer-Setup.exe` | Run it; tick "Add a shortcut to the Desktop" |

Each person's settings (Drive link, Google sign-in, company list, history) are kept outside
the app, so installing a newer version keeps them:

- Mac: `~/Library/Application Support/Drive Organizer`
- Windows: `%APPDATA%\Drive Organizer`

## What still has to be set up on each computer

- **Tailscale**, signed in to your network, if the reading model runs on another computer.
  Then paste that computer's address in Settings > Reading model server.
- **Google access file** (`credentials.json`): Settings > "Add Google access file".

## First open

The apps are not signed with a paid Apple or Microsoft certificate, so each computer warns once:

- **Mac:** the first double-click is blocked. Open System Settings > Privacy & Security, scroll
  to Security, and click "Open Anyway" (it may ask for an administrator password). After that
  it opens normally. An Apple Developer account ($99 a year) removes this step.
- **Windows:** on the blue "Windows protected your PC" box, click "More info", then "Run anyway".

## Building

A Mac app can only be built on a Mac, and a Windows app only on Windows.

**On GitHub (builds both):** every push builds both apps. Open the Actions tab, click the newest
"Build apps" run, and download the two files at the bottom of the page. Pushing a tag such as `v1.0` also puts them in a draft on the Releases
page; press Publish there and that page is the one link to share.

**On this Mac:**

    source .venv/bin/activate
    pip install pyinstaller
    packaging/build_mac.sh          # → dist/Drive-Organizer-Mac.dmg

**On a Windows PC** (with Python and Inno Setup installed):

    pip install -r requirements.txt pyinstaller
    python -m PyInstaller packaging/drive_organizer.spec --noconfirm
    iscc packaging\windows_installer.iss      &rem → dist\Drive-Organizer-Setup.exe

The recipes are in `packaging/` and `.github/workflows/build.yml`.

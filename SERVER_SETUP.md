# Run the model on a cloud server (no Ollama on your PCs)

The PDF renamer does OCR and company matching on your PC. Only the **letter text** is sent to
your own server, which runs the model and replies with the sender's name. If the text does not
show the sender and the server has the vision model (`ollama pull gemma4`), pictures of the first
two pages are sent as well, so the model can read a logo or stamp.

```
 Your PC (scan → OCR → text) ──Tailscale, encrypted──▶ Cloud server (Ollama + qwen3:4b)
```

Tailscale is a free private network: only devices signed in to *your* Tailscale account can
reach the server. Ollama has no password, so **never** open its port (11434) to the internet.

There are two ways to host the model: a free Oracle cloud server (sections 1–3), or a Mac you
already own (see **A Mac mini as the server**, further down — no cloud account needed).

## 1. Create a free server (Oracle Cloud Always Free)

1. Sign up at https://www.oracle.com/cloud/free/ (a card is needed for verification; you aren't charged
   for Always Free resources).
2. **Compute → Instances → Create instance**
   - Image: **Canonical Ubuntu 24.04**
   - Shape: **Ampere (VM.Standard.A1.Flex)** — as many OCPUs/GB as the Always Free limit allows
     (check the current limit on the shape page; 2 OCPU / 12 GB is enough).
   - Boot volume: 50 GB (the default) is fine.
   - Download the SSH private key it offers.
   - "Out of capacity"? Try another availability domain, or retry later. A free account is tied to
     one region, so if every domain there is full, use the Mac mini option below instead.
3. Leave the network's Security List as is (only SSH, port 22, open).

> **Idle reclaim:** Oracle may take back Always Free machines that stay almost idle for 7 days.
> The setup script keeps the model loaded in memory, which helps. Upgrading the account to
> *Pay As You Go* reportedly stops reclaims, and Always Free resources stay free.

## 2. Set up the server (once)

From your Mac's Terminal, in the project folder:

```bash
chmod 600 ~/Downloads/ssh-key-*.key
scp -i ~/Downloads/ssh-key-*.key scripts/setup_ollama_server.sh ubuntu@<SERVER-PUBLIC-IP>:
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<SERVER-PUBLIC-IP>
bash setup_ollama_server.sh
```

It prints a Tailscale login link: open it and sign in. At the end it prints the line for your `.env`.

## 3. Set up each PC

1. Install Tailscale from https://tailscale.com/download and sign in with the **same account**.
2. In the project's `.env`, add the line the script printed, e.g.
   ```
   OLLAMA_URL=http://100.101.102.103:11434
   ```
3. Check speed and correctness (made-up letters only):
   ```bash
   python3 scripts/server_speed_test.py
   ```
   For comparison, an M1 Mac takes about 1–2 s for a typical letter and ~14 s for the long one.
   A CPU-only server will be slower.
4. Rename as usual: `python3 ai_pdf_renamer.py --dry-run`

To go back to Ollama on this Mac, delete the `OLLAMA_URL` line from `.env`.

## A Mac mini as the server

Same idea as above, but the model runs on a Mac that stays on at home or in the office:

```
 Your PC (scan → OCR → text) ──Tailscale, encrypted──▶ Mac mini (Ollama + qwen3:4b)
```

**What the mini sees:** the OCR text of each letter and the name of the company that letter is
addressed to (one name per letter, never the whole company list). It never sees the PDFs.

**You need:** the mini plugged in and **logged in** (the server starts when you log in, not at
power-on, so after a restart log in once), Ollama installed and opened once, and Tailscale on the
mini and on every PC.

### On the mini (once)

1. Install Tailscale from https://tailscale.com/download and sign in. (Tailscale's page doesn't say
   whether installing on macOS needs an administrator password; if it asks, use an admin account.)
2. Quit the Ollama menu bar app (icon → Quit Ollama) and remove it from System Settings →
   General → Login Items. The script runs its own Ollama server on the same port.
3. Copy the project (or just `scripts/setup_mac_mini_server.sh`) to the mini, then:
   ```bash
   bash scripts/setup_mac_mini_server.sh --dry-run   # shows what it would do; changes nothing
   bash scripts/setup_mac_mini_server.sh
   ```
   It sets up a background service for your user (no administrator password, no Homebrew) that:
   - listens **only on the mini's Tailscale address**, so nothing on your home Wi-Fi can reach it
     (if Tailscale isn't connected yet it fails and retries; it never falls back to listening everywhere),
   - keeps the model loaded and answers one letter at a time,
   - keeps the Mac awake while it runs,
   - downloads `qwen3:4b` if it's missing, then prints the `OLLAMA_URL=` line for the PCs.

   Remove it with `--remove`. `--all-interfaces` listens on every address instead (the home
   network can reach it too); use it only if you must.

### On each PC

Follow section 3 above (same Tailscale account, the `OLLAMA_URL=` line in `.env` — or paste the address
in the app under **Settings → Reading model server**, which also tests it — then
`python3 scripts/server_speed_test.py`). Use the mini's Tailscale number in `OLLAMA_URL`; the mini's
name (`http://mac-mini:11434`) only works if MagicDNS is on. Speed depends on the mini's chip.

### Other people's PCs

Share only the mini, not your whole Tailscale network: in the Tailscale admin console open
**Machines → the mini → Share…** and send the invite. They install Tailscale on their PC, accept it
in their own Tailscale account, and put `OLLAMA_URL=http://<the mini's address shown in their
Tailscale app>:11434` in their `.env`. Shared devices are one-way: they can reach the mini; the
mini can't start connections to their PCs.

Limit them to the model port in **Access controls** (replace the address with the mini's):

```json
{ "src": ["autogroup:shared"], "dst": ["100.x.y.z"], "ip": ["11434"] }
```

Tailscale's documentation uses `autogroup:shared` for people you've shared devices with but doesn't
confirm a single-address `dst`, so after saving, check from their PC that port 11434 answers and
another port (for example 22) doesn't.

Two honest limits: Ollama has no login, so anyone who can reach port 11434 can use all of it,
including downloading or deleting models; share only with people you trust. And the text of
**their** clients' letters passes through **your** mini, so tell them, and only do this if they
are comfortable with it.

### Checks and problems

- On the mini, confirm it's Tailscale-only: `lsof -nP -iTCP:11434 -sTCP:LISTEN` should show
  `100.x.y.z:11434`, not `*:11434`.
- From a PC: `curl http://<mini address>:11434/api/tags` should list `qwen3:4b`.
- After a restart of the mini: log in; once Tailscale is connected the service starts within about 15 s.
- Log: `~/Library/Logs/DriveOrganizerOllama.log`.
- Never forward port 11434 on your router.

## Notes

- **OCR runs on each PC**: Apple Vision on a Mac, RapidOCR on Windows (installed by the launcher).
- **Change model:** on the server `ollama pull <model>`, then set `LOCAL_MODEL` in `ai_pdf_renamer.py`.
- **Server down / Tailscale off:** the renamer stops with "Can't reach the Ollama server" and renames nothing.

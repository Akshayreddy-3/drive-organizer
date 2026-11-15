# Run the model on a cloud server (no Ollama on your PCs)

The PDF renamer does OCR and company matching on your PC. Only the **letter text** is sent to
your own server, which runs the model and replies with the sender's name. PDFs never leave your PC.

```
 Your PC (scan → OCR → text) ──Tailscale, encrypted──▶ Cloud server (Ollama + qwen3:4b)
```

Tailscale is a free private network: only devices signed in to *your* Tailscale account can
reach the server. Ollama has no password, so **never** open its port (11434) to the internet.

## 1. Create a free server (Oracle Cloud Always Free)

1. Sign up at https://www.oracle.com/cloud/free/ (a card is needed for verification; you aren't charged
   for Always Free resources).
2. **Compute → Instances → Create instance**
   - Image: **Canonical Ubuntu 24.04**
   - Shape: **Ampere (VM.Standard.A1.Flex)** — as many OCPUs/GB as the Always Free limit allows
     (check the current limit on the shape page; 2 OCPU / 12 GB is enough).
   - Boot volume: 50 GB (the default) is fine.
   - Download the SSH private key it offers.
   - "Out of capacity"? Try another availability domain, or retry later.
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

## Notes

- **OCR runs on each PC**: Apple Vision on a Mac, RapidOCR on Windows (installed by the launcher).
- **Change model:** on the server `ollama pull <model>`, then set `LOCAL_MODEL` in `ai_pdf_renamer.py`.
- **Server down / Tailscale off:** the renamer stops with "Can't reach the Ollama server" and renames nothing.

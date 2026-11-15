#!/usr/bin/env bash
# setup_ollama_server.sh — run ONCE on the cloud server (Ubuntu, e.g. Oracle Always Free ARM).
# Installs Tailscale + Ollama, downloads the model, and lets ONLY your Tailscale devices reach it.
#
#   bash setup_ollama_server.sh            # uses qwen3:4b
#   bash setup_ollama_server.sh qwen3.5:4b # or another model
set -euo pipefail
MODEL="${1:-qwen3:4b}"

echo "== 1/4 Tailscale (private network between your PCs and this server)"
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up            # prints a login link the first time — open it and sign in
TS_IP="$(tailscale ip -4)"

echo "== 2/4 Ollama"
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
# Listen on all interfaces, keep the model loaded (faster answers; also keeps memory use above
# Oracle's idle threshold), and answer one letter at a time (small CPU).
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null <<'CONF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_KEEP_ALIVE=-1"
Environment="OLLAMA_NUM_PARALLEL=1"
CONF
sudo systemctl daemon-reload
sudo systemctl enable --now ollama
sudo systemctl restart ollama

echo "== 3/4 Firewall: Ollama port open on Tailscale only (it has no password)"
sudo iptables -C INPUT -i tailscale0 -p tcp --dport 11434 -j ACCEPT 2>/dev/null \
  || sudo iptables -I INPUT -i tailscale0 -p tcp --dport 11434 -j ACCEPT
if command -v netfilter-persistent >/dev/null; then sudo netfilter-persistent save; fi

echo "== 4/4 Downloading $MODEL (a few GB)"
for _ in $(seq 1 30); do curl -sf http://127.0.0.1:11434/api/tags >/dev/null && break; sleep 1; done
ollama pull "$MODEL"

echo
echo "✅ Done. On each PC, put this line in the project's .env:"
echo "   OLLAMA_URL=http://$TS_IP:11434"
echo "   (or use this server's Tailscale name: http://$(hostname):11434)"
echo "⚠️  Never open port 11434 in Oracle's Security List — Tailscale is the only way in."

#!/usr/bin/env bash
# Install instagram-mcp as a systemd service on a Debian or Ubuntu host.
#
#   curl -fsSL https://raw.githubusercontent.com/thenavidm/instagram-mcp/main/deploy/install.sh | sudo bash
#
# It installs the package, creates a dedicated user, writes a unit that listens
# on localhost only, and prints what you still have to do by hand.
set -euo pipefail

SERVICE=instagram-mcp
USER_NAME=igmcp
HOME_DIR=/var/lib/$SERVICE
PORT="${PORT:-8790}"
UNOFFICIAL="${UNOFFICIAL:-0}"

[[ $EUID -eq 0 ]] || { echo "Run with sudo."; exit 1; }

echo "==> Installing uv and the package"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh -s -- --no-modify-path
export PATH="/root/.local/bin:$PATH"

if [[ "$UNOFFICIAL" = "1" ]]; then
  uv tool install --force "thenavidm-instagram-mcp[unofficial]"
else
  uv tool install --force thenavidm-instagram-mcp
fi
BIN=$(command -v instagram-mcp || echo /root/.local/bin/instagram-mcp)

echo "==> Creating the service user"
id -u "$USER_NAME" >/dev/null 2>&1 || useradd --system --home "$HOME_DIR" --create-home --shell /usr/sbin/nologin "$USER_NAME"
install -d -o "$USER_NAME" -g "$USER_NAME" -m 700 "$HOME_DIR"

if [[ ! -f "$HOME_DIR/env" ]]; then
  echo "==> Writing $HOME_DIR/env"
  cat > "$HOME_DIR/env" <<ENV
# Fill these in, then: systemctl restart $SERVICE
# One account:
IG_ACCESS_TOKEN=
IG_USER_ID=
# Or several, a JSON array. See section 9 of the README.
#IG_ACCOUNTS_FILE=$HOME_DIR/accounts.json
#IG_PREFERRED=

IG_MCP_DATA_DIR=$HOME_DIR/data
IG_AUDIT_LOG=$HOME_DIR/data/audit.log

# Uncomment to remove every write tool from the list.
#IG_READ_ONLY=1

# Uncomment only after reading section 8. Against Instagram's terms.
#IG_UNOFFICIAL=1
ENV
  chown "$USER_NAME:$USER_NAME" "$HOME_DIR/env"
  chmod 600 "$HOME_DIR/env"
fi
install -d -o "$USER_NAME" -g "$USER_NAME" -m 700 "$HOME_DIR/data"

echo "==> Writing the unit"
cat > /etc/systemd/system/$SERVICE.service <<UNIT
[Unit]
Description=Instagram MCP server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
EnvironmentFile=$HOME_DIR/env
ExecStart=$BIN --http --host 127.0.0.1 --port $PORT
Restart=on-failure
RestartSec=5

# The data directory holds Instagram tokens and, on the unofficial tier, a
# logged-in session. Keep the rest of the filesystem out of reach.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$HOME_DIR
PrivateDevices=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now $SERVICE

cat <<DONE

Installed. It listens on 127.0.0.1:$PORT and nothing else.

Still to do:

  1. Put your token in $HOME_DIR/env, then:
       systemctl restart $SERVICE

  2. Check it:
       sudo -u $USER_NAME $BIN doctor

  3. Put a reverse proxy in front of it with TLS and authentication.
     This server has no authentication of its own, and it holds tokens
     that can post as you. Do not expose $PORT directly.

  Logs:   journalctl -u $SERVICE -f
  Status: systemctl status $SERVICE

DONE

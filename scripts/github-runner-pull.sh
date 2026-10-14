#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="${RUNNER_REPO_DIR:-$DEFAULT_REPO_DIR}"
REMOTE="${RUNNER_REMOTE:-origin}"
BRANCH="${RUNNER_BRANCH:-main}"

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "Repository not found at $REPO_DIR" >&2
  exit 1
fi

git config --global --add safe.directory "$REPO_DIR" || true
git -C "$REPO_DIR" fetch --prune "$REMOTE" "$BRANCH"
git -C "$REPO_DIR" checkout "$BRANCH"
git -C "$REPO_DIR" reset --hard "$REMOTE/$BRANCH"
git -C "$REPO_DIR" clean -fd

echo "Pulled $REMOTE/$BRANCH into $REPO_DIR"
git -C "$REPO_DIR" rev-parse --short HEAD

# Sync scripts and routing configs to host system
SUDO_CMD=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    SUDO_CMD="sudo"
  fi
fi

if [ -f "$REPO_DIR/scripts/hotspot-manager.py" ]; then
  $SUDO_CMD cp -f "$REPO_DIR/scripts/hotspot-manager.py" /usr/local/bin/hotspot-manager.py 2>/dev/null || true
  $SUDO_CMD chmod 0755 /usr/local/bin/hotspot-manager.py 2>/dev/null || true
fi
if [ -d "$REPO_DIR/scripts/hotspot" ]; then
  $SUDO_CMD mkdir -p /usr/local/lib/hotspot /usr/local/bin/hotspot 2>/dev/null || true
  $SUDO_CMD cp -rf "$REPO_DIR/scripts/hotspot/"* /usr/local/lib/hotspot/ 2>/dev/null || true
  $SUDO_CMD cp -rf "$REPO_DIR/scripts/hotspot/"* /usr/local/bin/hotspot/ 2>/dev/null || true
fi
if [ -d "$REPO_DIR/configs/routes" ]; then
  $SUDO_CMD mkdir -p /etc/goodwifi/routes 2>/dev/null || true
  $SUDO_CMD cp -rf "$REPO_DIR/configs/routes/"* /etc/goodwifi/routes/ 2>/dev/null || true
fi
if [ -f "$REPO_DIR/scripts/github-vpn-routes.sh" ]; then
  $SUDO_CMD cp -f "$REPO_DIR/scripts/github-vpn-routes.sh" /usr/local/bin/github-vpn-routes.sh 2>/dev/null || true
  $SUDO_CMD chmod 0755 /usr/local/bin/github-vpn-routes.sh 2>/dev/null || true
fi
if [ -f "$REPO_DIR/scripts/apply-routes.sh" ]; then
  $SUDO_CMD cp -f "$REPO_DIR/scripts/apply-routes.sh" /usr/local/bin/apply-routes.sh 2>/dev/null || true
  $SUDO_CMD chmod 0755 /usr/local/bin/apply-routes.sh 2>/dev/null || true
  $SUDO_CMD /usr/local/bin/apply-routes.sh 2>/dev/null || true
fi
if [ -f "$REPO_DIR/configs/90-hotspot-vpn-policy" ]; then
  $SUDO_CMD cp -f "$REPO_DIR/configs/90-hotspot-vpn-policy" /etc/NetworkManager/dispatcher.d/90-hotspot-vpn-policy 2>/dev/null || true
  $SUDO_CMD chmod 0755 /etc/NetworkManager/dispatcher.d/90-hotspot-vpn-policy 2>/dev/null || true
  $SUDO_CMD /etc/NetworkManager/dispatcher.d/90-hotspot-vpn-policy apply 2>/dev/null || true
fi

# Clean up legacy ipsets and config keys on Pi host if migrating
if [ -f /etc/goodwifi/goodwifi.conf ]; then
  $SUDO_CMD sed -i '/^GITHUB_IPSET=/d' /etc/goodwifi/goodwifi.conf 2>/dev/null || true
fi
if command -v ipset >/dev/null 2>&1; then
  for legacy_set in github_vpn_routes local_bypass_domains; do
    if $SUDO_CMD ipset list "$legacy_set" >/dev/null 2>&1; then
      $SUDO_CMD ipset flush "$legacy_set" 2>/dev/null || true
      $SUDO_CMD ipset destroy "$legacy_set" 2>/dev/null || true
    fi
  done
fi

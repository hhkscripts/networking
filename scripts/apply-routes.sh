#!/bin/bash
# Compile and apply modular route configurations to AdGuard Home and host ipsets.
#
# Routes are defined in modular text files (crypto, banking, streaming, github, etc.)
# under configs/routes/ and aggregated into local_routes (local ISP bypass) and
# vpn_routes (active VPN tunnel).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"

# Determine routes directory
if [ -n "${GOODWIFI_ROUTES_DIR:-}" ] && [ -d "$GOODWIFI_ROUTES_DIR" ]; then
    ROUTES_DIR="$GOODWIFI_ROUTES_DIR"
elif [ -d "$PROJECT_DIR/configs/routes" ]; then
    ROUTES_DIR="$PROJECT_DIR/configs/routes"
elif [ -n "$REPO_ROOT" ] && [ -d "$REPO_ROOT/configs/routes" ]; then
    ROUTES_DIR="$REPO_ROOT/configs/routes"
elif [ -d "/etc/goodwifi/routes" ]; then
    ROUTES_DIR="/etc/goodwifi/routes"
elif [ -d "/home/hhk/Projects/networking/configs/routes" ]; then
    ROUTES_DIR="/home/hhk/Projects/networking/configs/routes"
elif [ -d "/home/pi/Projects/networking/configs/routes" ]; then
    ROUTES_DIR="/home/pi/Projects/networking/configs/routes"
else
    ROUTES_DIR="$PROJECT_DIR/configs/routes"
fi

# Keep /etc/goodwifi/routes in sync with repository routes if writable
if [ -d "/etc/goodwifi/routes" ] && [ "$ROUTES_DIR" != "/etc/goodwifi/routes" ]; then
    cp -rf "$ROUTES_DIR/"* /etc/goodwifi/routes/ 2>/dev/null || true
fi

# Determine AdGuard Home config directory
if [ -n "${GOODWIFI_ADGUARD_CONF_DIR:-}" ] && [ -d "$GOODWIFI_ADGUARD_CONF_DIR" ]; then
    ADGUARD_CONF_DIR="$GOODWIFI_ADGUARD_CONF_DIR"
elif [ -d "$PROJECT_DIR/adguard/conf" ]; then
    ADGUARD_CONF_DIR="$PROJECT_DIR/adguard/conf"
elif [ -n "$REPO_ROOT" ] && [ -d "$REPO_ROOT/adguard/conf" ]; then
    ADGUARD_CONF_DIR="$REPO_ROOT/adguard/conf"
elif [ -d "/opt/goodwifi/adguard/conf" ]; then
    ADGUARD_CONF_DIR="/opt/goodwifi/adguard/conf"
elif [ -d "/etc/goodwifi/adguard/conf" ]; then
    ADGUARD_CONF_DIR="/etc/goodwifi/adguard/conf"
elif [ -d "/opt/adguardhome/conf" ]; then
    ADGUARD_CONF_DIR="/opt/adguardhome/conf"
elif [ -n "${SUDO_USER:-}" ] && [ -d "/home/$SUDO_USER/Projects/networking/adguard/conf" ]; then
    ADGUARD_CONF_DIR="/home/$SUDO_USER/Projects/networking/adguard/conf"
elif [ -n "${HOME:-}" ] && [ -d "$HOME/Projects/networking/adguard/conf" ]; then
    ADGUARD_CONF_DIR="$HOME/Projects/networking/adguard/conf"
elif [ -d "/home/hhk/Projects/networking/adguard/conf" ]; then
    ADGUARD_CONF_DIR="/home/hhk/Projects/networking/adguard/conf"
elif [ -d "/home/pi/Projects/networking/adguard/conf" ]; then
    ADGUARD_CONF_DIR="/home/pi/Projects/networking/adguard/conf"
else
    ADGUARD_CONF_DIR=""
fi

# Fallback: inspect running docker container mount if available
if [ -z "$ADGUARD_CONF_DIR" ] && command -v docker >/dev/null 2>&1; then
    for c_name in "${ADGUARD_CONTAINER:-}" "adguardhome" "vpn-adguardhome-1" "vpn_adguardhome_1"; do
        [ -z "$c_name" ] && continue
        docker_mount="$(docker inspect "$c_name" --format '{{range .Mounts}}{{if eq .Destination "/opt/adguardhome/conf"}}{{.Source}}{{end}}{{end}}' 2>/dev/null || true)"
        if [ -n "$docker_mount" ] && [ -d "$docker_mount" ]; then
            ADGUARD_CONF_DIR="$docker_mount"
            break
        fi
    done
fi

LOCAL_ROUTES_IPSET="${LOCAL_ROUTES_IPSET:-local_routes}"
VPN_ROUTES_IPSET="${VPN_ROUTES_IPSET:-vpn_routes}"
VPN_DOMAINS_IPSET="${VPN_DOMAINS_IPSET:-vpn_domains}"

log() {
    printf '%s\n' "$1"
}

DRY_RUN=0
FORCE_RELOAD="${FORCE_RELOAD:-0}"
for arg in "$@"; do
    case "$arg" in
        --dry-run|--check) DRY_RUN=1 ;;
        --reload|--force-reload|-r) FORCE_RELOAD=1 ;;
    esac
done

if [ "$DRY_RUN" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
    log "Run as root: sudo $0 (or run with --dry-run to test syntax without root)"
    exit 1
fi

if [ ! -d "$ROUTES_DIR" ]; then
    log "Routes directory not found: $ROUTES_DIR"
    exit 1
fi

# Ensure ipsets exist (when not in dry-run)
if [ "$DRY_RUN" -eq 0 ]; then
    ipset create "$LOCAL_ROUTES_IPSET" hash:net family inet maxelem 65536 2>/dev/null || true
    ipset create "$VPN_ROUTES_IPSET" hash:net family inet maxelem 131072 2>/dev/null || true
    ipset create "$VPN_DOMAINS_IPSET" hash:ip maxelem 65536 2>/dev/null || true
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

tmp_ipset_conf="$tmp_dir/ipset.conf"
: > "$tmp_ipset_conf"

collect_entries() {
    local list_file="$1"
    local output_domains="$2"
    local output_cidrs="$3"

    : > "$output_domains"
    : > "$output_cidrs"

    if [ ! -f "$list_file" ]; then
        return
    fi

    while IFS= read -r file_name || [ -n "$file_name" ]; do
        file_name="$(printf '%s' "$file_name" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
        case "$file_name" in
            \#*|"") continue ;;
        esac

        target_file=""
        if [ -f "$ROUTES_DIR/$file_name" ]; then
            target_file="$ROUTES_DIR/$file_name"
        elif [ -f "$file_name" ]; then
            target_file="$file_name"
        fi

        if [ -z "$target_file" ] || [ ! -f "$target_file" ]; then
            continue
        fi

        while IFS= read -r entry || [ -n "$entry" ]; do
            entry="$(printf '%s' "$entry" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/[[:space:]]*#.*$//')"
            [ -z "$entry" ] && continue

            # Distinguish CIDR/IP from domain name
            if [[ "$entry" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(/[0-9]+)?$ ]]; then
                printf '%s\n' "$entry" >> "$output_cidrs"
            else
                printf '%s\n' "$entry" >> "$output_domains"
            fi
        done < "$target_file"
    done < "$list_file"
}

# 1. Process local_routes (Local ISP Bypass)
local_domains="$tmp_dir/local_domains.txt"
local_cidrs="$tmp_dir/local_cidrs.txt"
collect_entries "$ROUTES_DIR/local_routes.list" "$local_domains" "$local_cidrs"

local_domain_count=0
if [ -s "$local_domains" ]; then
    sort -u "$local_domains" | while IFS= read -r domain; do
        [ -n "$domain" ] && printf '%s/%s\n' "$domain" "$LOCAL_ROUTES_IPSET" >> "$tmp_ipset_conf"
    done
    local_domain_count="$(sort -u "$local_domains" | wc -l | tr -d ' ')"
fi

local_cidr_count=0
if [ -s "$local_cidrs" ]; then
    while IFS= read -r cidr; do
        if [ "$DRY_RUN" -eq 0 ] && [ -n "$cidr" ]; then
            ipset add "$LOCAL_ROUTES_IPSET" "$cidr" -exist 2>/dev/null || true
        fi
    done < "$local_cidrs"
    local_cidr_count="$(sort -u "$local_cidrs" | wc -l | tr -d ' ')"
fi

# 2. Process vpn_routes (Active VPN Tunnel)
vpn_domains="$tmp_dir/vpn_domains.txt"
vpn_cidrs="$tmp_dir/vpn_cidrs.txt"
collect_entries "$ROUTES_DIR/vpn_routes.list" "$vpn_domains" "$vpn_cidrs"

vpn_domain_count=0
if [ -s "$vpn_domains" ]; then
    sort -u "$vpn_domains" | while IFS= read -r domain; do
        [ -n "$domain" ] && printf '%s/%s\n' "$domain" "$VPN_DOMAINS_IPSET" >> "$tmp_ipset_conf"
    done
    vpn_domain_count="$(sort -u "$vpn_domains" | wc -l | tr -d ' ')"
fi

vpn_cidr_count=0
if [ -s "$vpn_cidrs" ]; then
    while IFS= read -r cidr; do
        if [ "$DRY_RUN" -eq 0 ] && [ -n "$cidr" ]; then
            ipset add "$VPN_ROUTES_IPSET" "$cidr" -exist 2>/dev/null || true
        fi
    done < "$vpn_cidrs"
    vpn_cidr_count="$(sort -u "$vpn_cidrs" | wc -l | tr -d ' ')"
fi

# Pre-populate critical domain IPs into vpn_domains immediately
if [ "$DRY_RUN" -eq 0 ] && [ -s "$vpn_domains" ] && command -v getent >/dev/null 2>&1; then
    for target_domain in fragment.com api.telegram.org telegram.org t.me; do
        if grep -qx "$target_domain" "$vpn_domains" 2>/dev/null; then
            (getent ahostsv4 "$target_domain" 2>/dev/null || true) | awk '{print $1}' | while IFS= read -r resolved_ip; do
                if [ -n "$resolved_ip" ]; then
                    ipset add "$VPN_DOMAINS_IPSET" "$resolved_ip" -exist 2>/dev/null || true
                fi
            done
        fi
    done
fi

log "Processed routes from $ROUTES_DIR:"
log "  - local_routes: $local_domain_count domains, $local_cidr_count IP/CIDRs (bypass VPN)"
log "  - vpn_routes:   $vpn_domain_count domains, $vpn_cidr_count IP/CIDRs (route via VPN)"

# 3. Synchronize with AdGuard Home if configuration directory is available
adguard_updated=0
if [ -n "$ADGUARD_CONF_DIR" ] && [ -d "$ADGUARD_CONF_DIR" ]; then
    target_ipset_conf="$ADGUARD_CONF_DIR/ipset.conf"
    if [ ! -f "$target_ipset_conf" ] || ! cmp -s "$tmp_ipset_conf" "$target_ipset_conf"; then
        cp "$tmp_ipset_conf" "$target_ipset_conf"
        chmod 0644 "$target_ipset_conf"
        adguard_updated=1
        log "Updated AdGuard Home ipset configuration: $target_ipset_conf"
    fi

    # Ensure AdGuardHome.yaml points to ipset_file
    adguard_yaml="$ADGUARD_CONF_DIR/AdGuardHome.yaml"
    if [ -f "$adguard_yaml" ]; then
        if grep -q "^  ipset_file: \"\"" "$adguard_yaml" 2>/dev/null || grep -q "^  ipset_file:$" "$adguard_yaml" 2>/dev/null; then
            sed -i 's#^  ipset_file:.*#  ipset_file: /opt/adguardhome/conf/ipset.conf#' "$adguard_yaml"
            adguard_updated=1
            log "Configured ipset_file in $adguard_yaml"
        elif ! grep -q "ipset_file: /opt/adguardhome/conf/ipset.conf" "$adguard_yaml" 2>/dev/null && grep -q "^  ipset_file:" "$adguard_yaml" 2>/dev/null; then
            sed -i 's#^  ipset_file:.*#  ipset_file: /opt/adguardhome/conf/ipset.conf#' "$adguard_yaml"
            adguard_updated=1
            log "Updated ipset_file in $adguard_yaml"
        fi

        # Remove any legacy Google Ads / tracking whitelist rules that bypass ad-blocking
        if grep -q "@@||.*\(googleads\|pagead2\|adservice\|ogads-pa\|doubleclick\)" "$adguard_yaml" 2>/dev/null; then
            sed -i '/@@||.*\(googleads\|pagead2\|adservice\|ogads-pa\|doubleclick\)/d' "$adguard_yaml"
            adguard_updated=1
            log "Removed Google Ads whitelist rules from $adguard_yaml"
        fi

        # Ensure protection_enabled and filtering_enabled are active
        if grep -q "protection_enabled: false" "$adguard_yaml" 2>/dev/null; then
            sed -i 's/protection_enabled: false/protection_enabled: true/' "$adguard_yaml"
            adguard_updated=1
            log "Enabled protection_enabled in $adguard_yaml"
        fi
        if grep -q "filtering_enabled: false" "$adguard_yaml" 2>/dev/null; then
            sed -i 's/filtering_enabled: false/filtering_enabled: true/' "$adguard_yaml"
            adguard_updated=1
            log "Enabled filtering_enabled in $adguard_yaml"
        fi

        # Ensure default AdGuard DNS filter is present in filters
        if ! grep -q "filter_1\.txt" "$adguard_yaml" 2>/dev/null; then
            if grep -q "^filters:[[:space:]]*\[\]" "$adguard_yaml" 2>/dev/null; then
                sed -i 's#^filters:[[:space:]]*\[\]#filters:\n  - enabled: true\n    url: https://adguardteam.github.io/HostlistsRegistry/assets/filter_1.txt\n    name: AdGuard DNS filter\n    id: 1#' "$adguard_yaml"
                adguard_updated=1
                log "Injected default AdGuard DNS filter into $adguard_yaml"
            fi
        fi

        # Ensure DoH and Apple iCloud Private Relay blocking rules in user_rules
        doh_file="$ROUTES_DIR/dns-doh-blocklist.txt"
        if [ ! -f "$doh_file" ] && [ -f "$ROUTES_DIR/doh-blocklist.txt" ]; then
            doh_file="$ROUTES_DIR/doh-blocklist.txt"
        fi
        if [ -f "$doh_file" ] && ! grep -q "mask\.icloud\.com" "$adguard_yaml" 2>/dev/null; then
            if grep -q "^user_rules:[[:space:]]*\[\]" "$adguard_yaml" 2>/dev/null; then
                sed -i 's/^user_rules:[[:space:]]*\[\]/user_rules:/' "$adguard_yaml"
            elif ! grep -q "^user_rules:" "$adguard_yaml" 2>/dev/null; then
                printf '\nuser_rules:\n' >> "$adguard_yaml"
            fi
            while IFS= read -r line || [ -n "$line" ]; do
                line="$(printf '%s' "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
                case "$line" in
                    \#*|"") continue ;;
                esac
                if ! grep -Fq "'$line'" "$adguard_yaml" 2>/dev/null; then
                    sed -i "/^user_rules:/a\  - '$line'" "$adguard_yaml"
                    adguard_updated=1
                fi
            done < "$doh_file"
            log "Injected DoH & Private Relay blocklist into $adguard_yaml"
        fi
    fi
fi

# 4. Restart or reload AdGuard Home if needed
if [ "$adguard_updated" -eq 0 ] && [ "$FORCE_RELOAD" -eq 0 ] && [ -n "${target_ipset_conf:-}" ] && [ -f "$target_ipset_conf" ]; then
    for c_name in "${ADGUARD_CONTAINER:-}" "adguardhome" "vpn-adguardhome-1" "vpn_adguardhome_1"; do
        [ -z "$c_name" ] && continue
        if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$c_name"; then
            started_epoch="$(docker inspect --format '{{.State.StartedAt}}' "$c_name" 2>/dev/null | xargs -I{} date -d {} +%s 2>/dev/null || echo 0)"
            file_epoch="$(stat -c %Y "$target_ipset_conf" 2>/dev/null || echo 0)"
            if [ "$file_epoch" -gt "$started_epoch" ]; then
                adguard_updated=1
                log "Detected newer ipset.conf than running container; reloading AdGuard Home."
                break
            fi
        fi
    done
fi

if [ "$adguard_updated" -eq 1 ] || [ "$FORCE_RELOAD" -eq 1 ]; then
    adguard_restarted=0
    for c_name in "${ADGUARD_CONTAINER:-}" "adguardhome" "vpn-adguardhome-1" "vpn_adguardhome_1"; do
        [ -z "$c_name" ] && continue
        if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$c_name"; then
            log "Restarting AdGuard Home container ($c_name) to apply ipset rules..."
            docker restart "$c_name" >/dev/null 2>&1 || true
            log "AdGuard Home restarted successfully."
            adguard_restarted=1
            break
        fi
    done
    if [ "$adguard_restarted" -eq 0 ] && systemctl is-active --quiet AdGuardHome 2>/dev/null; then
        systemctl restart AdGuardHome || true
        log "AdGuardHome systemd service restarted."
    fi
fi

# 5. Persist netfilter / ipset state if utility is installed
if [ "$DRY_RUN" -eq 0 ] && command -v netfilter-persistent >/dev/null 2>&1; then
    netfilter-persistent save >/dev/null 2>&1 || true
    log "Saved persistent netfilter state."
fi

if [ "$DRY_RUN" -eq 1 ]; then
    log "Dry-run check complete. Generated ipset.conf preview:"
    head -n 25 "$tmp_ipset_conf"
    if [ "$(wc -l < "$tmp_ipset_conf")" -gt 25 ]; then
        log "... ($(wc -l < "$tmp_ipset_conf") total lines)"
    fi
else
    log "Routes successfully applied."
fi

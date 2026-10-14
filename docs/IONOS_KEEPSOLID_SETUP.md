# Complete VPS + KeepSolid (VPN Unlimited) + 3x-ui Setup Guide

This guide documents the complete, verified, end-to-end configuration to run **KeepSolid VPN Unlimited** on a VPS with **3x-ui (Xray Reality)**, eliminating the Raspberry Pi Double Tunnel while preserving clean consumer exit IPs (Japan, Singapore, US, etc.) and preventing SSH lockouts.

---

## 1. System Architecture Overview

```mermaid
flowchart TD
    Client["Hotspot Client (Phone / PC)"] -->|Wi-Fi 10.42.0.0/24| Pi["Raspberry Pi (GoodWifi)"]
    Pi -->|Single VLESS Reality (Port 8443)| VPS["VPS (<YOUR_VPS_DOMAIN> / <SERVER_IP>)"]
    
    subgraph VPS_Internal ["VPS Internal Architecture"]
        Inbound["Inbound: in-8443-tcp (VLESS Reality)"]
        Router["Xray Routing: in-8443-tcp -> keepsolid"]
        OpenVPN["OpenVPN Client Service (tun0)"]
        Table100["Policy Table 100: Host SSH (2222) -> <INTERFACE_NAME>"]
        
        Inbound --> Router
        Router -->|SO_BINDTODEVICE tun0| OpenVPN
    end
    
    OpenVPN -->|KeepSolid Exit (JP / SG / US)| Web["Cloudflare / Target Services"]
```

---

## 2. Prerequisites & Placeholders

Throughout this guide, replace the following placeholders with your actual server configuration:
* `<SERVER_IP>`: Your VPS public IP address (or domain `<YOUR_VPS_DOMAIN>`, e.g. `connect.yourdomain.com`).
* `<SERVER_GATEWAY>`: Your VPS default gateway (e.g. `ip route show default`).
* `<INTERFACE_NAME>`: Your VPS primary physical network interface (e.g. `ens6`, `eth0`).
* `<SSH_PORT>`: Your VPS SSH port (e.g. `2222`).
* `<VLESS_PORT>`: Your VLESS Reality port (e.g. `8443`).
* `<PROFILES_DIR>`: `/etc/openvpn/client/`

---

## 3. Step 1: Copy Profiles from Project to VPS

Run from your local workstation terminal:
```bash
# Create directory on VPS
ssh -p <SSH_PORT> root@<SERVER_IP> "mkdir -p /etc/openvpn/client"

# Copy all profiles (48+ countries)
scp -P <SSH_PORT> -r profiles/* root@<SERVER_IP>:/etc/openvpn/client/

# Flatten profile hierarchy on VPS
ssh -p <SSH_PORT> root@<SERVER_IP> "cd /etc/openvpn/client && find . -mindepth 2 -type f -name '*.ovpn' -exec cp {} . \;"
```

---

## 4. Step 2: Configure Asymmetric Routing Immunity (Table 100 & rp_filter)

To prevent OpenVPN from ever breaking SSH on custom ports, configure **Policy Routing Table 100** and **Loose Reverse Path Filtering (`rp_filter = 2`)** on the VPS.

Run on the VPS:
```bash
# 1. Enable Loose Reverse Path Filtering
sudo sysctl -w net.ipv4.conf.all.rp_filter=2
sudo sysctl -w net.ipv4.conf.default.rp_filter=2
sudo sysctl -w net.ipv4.ip_forward=1

# Persist sysctl settings
sudo tee /etc/sysctl.d/99-vpn-routing.conf << 'EOF'
net.ipv4.conf.all.rp_filter = 2
net.ipv4.conf.default.rp_filter = 2
net.ipv4.ip_forward = 1
EOF

# 2. Configure Dedicated Table 100 for Host IP
sudo ip route add <SERVER_GATEWAY> dev <INTERFACE_NAME> scope link table 100 2>/dev/null || true
sudo ip route replace default via <SERVER_GATEWAY> dev <INTERFACE_NAME> table 100
sudo ip rule del from <SERVER_IP> table 100 priority 100 2>/dev/null || true
sudo ip rule add from <SERVER_IP> table 100 priority 100

# 3. Create a systemd service to re-apply Table 100 on boot
sudo tee /etc/systemd/system/policy-table100.service << 'EOF'
[Unit]
Description=Persistent Policy Routing Table 100 for Host SSH
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'GW=$(ip -4 route show default | awk "{print \$3; exit}"); IF=$(ip -4 route show default | awk "{print \$5; exit}"); IP=$(ip -4 addr show dev $IF | awk "/inet / {split(\$2, a, \"/\"); print a[1]; exit}"); ip route add $GW dev $IF scope link table 100 2>/dev/null || true; ip route replace default via $GW dev $IF table 100; ip rule del from $IP table 100 priority 100 2>/dev/null || true; ip rule add from $IP table 100 priority 100'

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable policy-table100.service
```

---

## 5. Step 3: Install OpenVPN and Country Switcher CLI (`switch-exit`)

Run on the VPS:
```bash
# Install OpenVPN & curl
sudo apt update && sudo apt install -y openvpn curl iptables

# Enable NAT masquerade for OpenVPN tunnel
sudo iptables -t nat -C POSTROUTING -o tun+ -j MASQUERADE 2>/dev/null || sudo iptables -t nat -A POSTROUTING -o tun+ -j MASQUERADE

# Disable SSH reverse DNS delay
echo "UseDNS no" | sudo tee /etc/ssh/sshd_config.d/no-dns.conf
sudo systemctl restart ssh

# Install switch-exit script
sudo tee /usr/local/bin/switch-exit << 'EOF'
#!/bin/bash
set -e

COUNTRY="${1:-jp}"
CONF_DIR="/etc/openvpn/client"

TARGET_FILE=$(find "$CONF_DIR" -maxdepth 1 -type f -name "${COUNTRY}*.ovpn" | head -n 1)

if [ -z "$TARGET_FILE" ] || [ ! -f "$TARGET_FILE" ]; then
    echo "❌ Error: Profile for country '$COUNTRY' not found in $CONF_DIR"
    echo "Available: $(ls $CONF_DIR/*.ovpn 2>/dev/null | xargs -n 1 basename | cut -d- -f1 | sort -u | xargs)"
    exit 1
fi

echo "🔄 Switching KeepSolid Exit to: $(basename "$TARGET_FILE")..."
systemctl stop openvpn-client@active 2>/dev/null || true

# Prepare active.conf
cp "$TARGET_FILE" "$CONF_DIR/active.conf"

systemctl restart openvpn-client@active
sleep 3

EXIT_IP=$(curl -s -m 5 --interface tun0 https://api.ipify.org 2>/dev/null || echo "negotiating...")
echo "✅ Successfully connected to $COUNTRY (Exit IP: $EXIT_IP)"
EOF

sudo chmod +x /usr/local/bin/switch-exit
```

---

## 6. Step 4: Configure 3x-ui / Xray Outbound on VPS

In 3x-ui, configure inbound `in-8443-tcp` to route out to `tun0` via a dedicated freedom outbound named `keepsolid`.

Run this Python script on the VPS to update the 3x-ui database cleanly:
```bash
python3 -c '
import sqlite3, json, shutil

shutil.copy2("/etc/x-ui/x-ui.db", "/etc/x-ui/x-ui.db.bak")
con = sqlite3.connect("/etc/x-ui/x-ui.db")
cur = con.cursor()
cur.execute("SELECT value FROM settings WHERE key=\"xrayTemplateConfig\";")
row = cur.fetchone()
cfg = json.loads(row[0])

# 1. Add keepsolid outbound if not present
tags = [o.get("tag") for o in cfg["outbounds"]]
if "keepsolid" not in tags:
    ks_out = {
        "tag": "keepsolid",
        "protocol": "freedom",
        "streamSettings": {
            "sockopt": {
                "interface": "tun0"
            }
        }
    }
    cfg["outbounds"].insert(0, ks_out)

# 2. Add routing rule for in-8443-tcp -> keepsolid
rule_exists = any(r.get("outboundTag") == "keepsolid" for r in cfg["routing"]["rules"])
if not rule_exists:
    rule = {
        "type": "field",
        "inboundTag": ["in-8443-tcp"],
        "outboundTag": "keepsolid"
    }
    cfg["routing"]["rules"].append(rule)

cur.execute("UPDATE settings SET value=? WHERE key=\"xrayTemplateConfig\";", (json.dumps(cfg, indent=2),))
con.commit()
con.close()
print("3x-ui database successfully configured!")
'

sudo systemctl restart x-ui
```

---

## 7. Step 5: Switch Raspberry Pi Hotspot to VPS Direct

Run on the **Raspberry Pi**:
```bash
# 1. Point primary VLESS Reality to Server 1
sudo hotspot-manager.py --reality-server 1

# 2. Remove local OpenVPN Double Tunnel (Pure Direct Reality)
sudo hotspot-manager.py --unlimited-country direct
```

---

## 8. Usage & Verification

### To change exit country at any time:
From VPS terminal:
```bash
switch-exit jp      # Switch to Japan
switch-exit sg      # Switch to Singapore
switch-exit us      # Switch to United States
switch-exit uk      # Switch to United Kingdom
```
Or remotely from the Raspberry Pi / Local workstation:
```bash
ssh -p <SSH_PORT> root@<SERVER_IP> switch-exit sg
```

### To check active exit IP:
On Raspberry Pi or any connected Wi-Fi device:
```bash
curl https://api.ipify.org
```
It will display the KeepSolid IP (e.g. Japan or Singapore exit).

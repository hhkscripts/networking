---
name: pi-live-diagnostics
description: Safely inspect, diagnose, and troubleshoot the live Raspberry Pi GoodWifi hotspot router over SSH. Use when verifying live WAN routing, checking VPN tunnels, inspecting AdGuard DNS, or viewing connected clients without interrupting network traffic.
---

# Raspberry Pi Live Diagnostics & Operations Skill

This skill provides verified, safe, and non-destructive diagnostic workflows for operating and troubleshooting the live Raspberry Pi GoodWifi hotspot router over SSH.

## Connection Invariant
- **Target Host**: `hhk@192.168.100.69`
- **SSH Command Pattern**: Always use non-interactive batch mode with short connect timeouts:
  ```bash
  ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "<command>"
  ```

---

## 1. Quick Full Diagnostic & Health Check
Run the unified health status command:
```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "sudo hotspot-manager.py -s"
```
Verifies:
- **Services**: hostapd (Wi-Fi AP), dnsmasq (DHCP), adguard (AdGuard Home container), telegrambot container.
- **VPN**: Backend protocol (sing0, awg0, tun0), tunnel IP, and actual exit IP.
- **Hotspot**: SSID and number of active connected client stations.
- **Network**: Active WAN uplink (Fiber eth0 vs Mobile USB usb0), DNS resolution, IPv6 protection mode, ping RTT to 8.8.8.8.

---

## 2. WAN Routing & Uplink Inspection
Check active WAN interface and reachability of both uplinks:
```bash
# 1. Check WAN state and reachability
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "sudo hotspot-manager.py --wan status"

# 2. Inspect kernel default routing table
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "ip -4 route show default table main"

# 3. Check physical carrier and DHCP IP assignments
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "ip -4 -brief addr show eth0 usb0"
```

### Expected Metric States
- **Primary Uplink**: Must have `metric 50`.
- **Standby Uplink**: Must have `metric 600`.
- **Unmetered Metric 0**: Must NOT exist on either interface.

---

## 3. Safe WAN Switching & Failover Testing
To manually switch or test failover:
```bash
# Force switch to Mobile USB (usb0)
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "sudo hotspot-manager.py --wan usb0"

# Force switch to Fiber (eth0)
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "sudo hotspot-manager.py --wan eth0"

# Auto-select best reachable uplink
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "sudo hotspot-manager.py --wan auto"
```

---

## 4. Background Watchdog Verification
Verify that the automated watchdog timer is active and inspecting health:
```bash
# Check timer status and next trigger time
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "systemctl status goodwifi-watchdog.timer"

# Run one-shot watchdog cycle manually
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "sudo hotspot-manager.py --watchdog"

# View recent watchdog logs
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "journalctl -u goodwifi-watchdog.service -n 30 --no-pager"
```

---

## 5. Connected Clients & Wi-Fi Stations
To see all connected client devices, MAC addresses, hostnames, and signal strengths:
```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "sudo hotspot-manager.py --clients"
```

---

## 6. Remote Synchronizing & Updating Pi Host
When repository changes are pushed to GitHub, sync and apply to the live Pi:
```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 hhk@192.168.100.69 "cd ~/Projects/vpn && sudo bash scripts/github-runner-pull.sh"
```
*(Note: `github-runner-pull.sh` automatically copies updated scripts to `/usr/local/bin` and `/usr/local/lib/hotspot`, reloads route policies, and gracefully applies local files even if the Pi is temporarily offline).*

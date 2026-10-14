# GoodWifi Raspberry Pi Self-Troubleshooting & Debugging Guide

This guide provides practical commands and workflows to inspect logs, diagnose network health, and debug issues on your GoodWifi hotspot by yourself.

---

## 1. Quick Health Inspection (တစ်ချက်တည်းဖြင့် အခြေအနေ စစ်ဆေးခြင်း)

Run the Hotspot Manager status command on the Pi:
```bash
sudo hotspot-manager.py -s
```
**What to look for:**
- `VPN: Connected: True` -> Active tunnel name (`sing0`, `awg0`, etc.) and VPN Exit IP.
- `Ping 8.8.8.8: Loss: 0%` -> Packet loss should be **0%**.
- `IPv6 Protection: REJECT` -> Should be **REJECT** (not DROP, to avoid Happy Eyeballs delays).
- `Clients: X` -> Number of devices currently connected.

---

## 2. Inspecting Live Service Logs (Log များကို တိုက်ရိုက် ကြည့်ရှုနည်း)

### (A) Sing-box (VPN Tunnel Gateway)
To monitor sing-box in real-time as traffic flows:
```bash
sudo journalctl -u sing-box -f
```
To check only errors and warnings from the last 50 lines:
```bash
sudo journalctl -u sing-box -n 50 --no-pager | grep -E 'WARN|ERROR'
```
To inspect logs since a specific time:
```bash
sudo journalctl -u sing-box --since "21:30:00" --no-pager
```

**Key Warning Signs in Sing-box Logs:**
| Log Message | Meaning | Fix |
| :--- | :--- | :--- |
| `endpoint is not ready yet` | OpenVPN tunnel restarted and client tried connecting before it was ready | Increase `ping_restart` or check server endpoint |
| `replayed gcm packet` | Packet reordering over SOCKS5 caused GCM replay drop | Enforce `AES-256-CBC` in profile |
| `invalid tls data packet hmac` | Jitter or packet corruption | Usually harmless if isolated; rotate IP if frequent |

---

### (B) Xray Core (VLESS Reality Layer)
To view real-time inbound connections and TLS handshakes:
```bash
sudo journalctl -u xray -f
```
To check recent accepted connections:
```bash
sudo journalctl -u xray -n 30 --no-pager
```
**What to look for:**
- `accepted tcp:<SERVER_IP>:8443 [socks-in >> server-1]` -> Xray is successfully routing through your VLESS Reality VPS.

---

### (C) AdGuard Home (DNS Security)
If running via Docker:
```bash
# View last 50 log entries
docker logs --tail 50 adguardhome

# Follow logs live
docker logs -f adguardhome
```
If running via systemd:
```bash
sudo journalctl -u AdGuardHome -f
```

---

### (D) Wi-Fi Hotspot & DHCP (hostapd & dnsmasq)
To check Wi-Fi client connection/disconnection events:
```bash
sudo journalctl -u hostapd -n 30 --no-pager
```
To check DHCP IP assignments to client phones/laptops:
```bash
sudo journalctl -u dnsmasq -n 30 --no-pager | grep DHCPACK
```

---

## 3. Network & Routing Diagnostics (ကွန်ရက်နှင့် Routing စစ်ဆေးနည်း)

### (A) Ping & MTU Test (Packet Loss & Fragmentation စစ်ဆေးခြင်း)
Test standard ping to Google DNS through active tunnel:
```bash
ping -c 5 -I sing0 8.8.8.8
```
Test MTU fragmentation with Don't Fragment flag (`-M do`):
```bash
# Test 1350 bytes (normal VPN packet payload)
ping -c 3 -M do -s 1350 -I sing0 8.8.8.8

# If 1350 fails with "Frag needed", test lower MTU (1280):
ping -c 3 -M do -s 1252 -I sing0 8.8.8.8
```

---

### (B) Policy Routing Tables Check (Routing မှန်မမှန် စစ်ဆေးခြင်း)
Verify routing rules priority:
```bash
ip rule show
```
Expected output hierarchy:
```text
997:  from 10.42.0.0/24 to 10.8.0.0/24 lookup main  (Management Bypass)
998:  from all fwmark 0x65 lookup main              (Banking/Binance Bypass)
999:  from all fwmark 0x64 lookup 100               (VPN Routes ipset)
1000: from 10.42.0.0/24 lookup 100                  (All Hotspot Clients -> Table 100)
```
Verify Table 100 default route points to active VPN interface:
```bash
ip route show table 100
```
Expected output:
```text
default dev sing0 scope link
```

---

### (C) DNS Resolution Check (AdGuard Home အလုပ်လုပ်မလုပ် စစ်ဆေးခြင်း)
Run a test DNS query against the Pi's AdGuard Home:
```bash
dig @10.42.0.1 google.com
# or
nslookup google.com 10.42.0.1
```
Check query response time at the bottom (`Query time: X msec`). It should be under 50ms.

---

### (D) Wi-Fi Power Save & Clock Synchronization Check
Check Wi-Fi chip power save mode:
```bash
iw dev wlan0 get power_save
```
*(Must be `Power save: off`. If on, clients experience latency spikes).*

Check system clock synchronization (Critical for VLESS Reality TLS handshakes):
```bash
timedatectl status
```
*(Look for `System clock synchronized: yes`).*

---

## 4. Quick Fix Commands (ပြဿနာကြုံလျှင် ချက်ချင်း ဖြေရှင်းနိုင်မည့် Command များ)

| Issue / လက္ခဏာ | အကြောင်းရင်း | ချက်ချင်း ဖြေရှင်းမည့် Command |
| :--- | :--- | :--- |
| **Connecting ဖြစ်ပြီး နှောင့်နှေးခြင်း** | IPv6 DROP ကြောင့် Timeout စောင့်နေရခြင်း | `sudo hotspot-manager.py --set-ipv6 reject` |
| **လိုင်းလေးနေခြင်း / IP ကျခြင်း** | ရွေးထားသော Exit IP endpoint က Latency များနေခြင်း | `sudo hotspot-manager.py --rotate-ip` |
| **VPN လုံးဝ အင်တာနက်မထွက်တော့ခြင်း** | Tunnel interface deadlock ဖြစ်သွားခြင်း | `sudo hotspot-manager.py -rv` (Restart VPN) |
| **Wi-Fi Ping 2000ms+ ခုန်တက်ခြင်း** | Wi-Fi power save auto-enabled | `sudo iw dev wlan0 set power_save off` |
| **အချိန်လွဲနေခြင်း (VLESS ချိတ်မရခြင်း)** | Pi reboot ပြီးနောက် NTP မမှီခြင်း | `sudo systemctl restart systemd-timesyncd` |
| **AdGuard DNS မထွက်ခြင်း** | AdGuard container ရပ်သွားခြင်း | `sudo hotspot-manager.py --adguard restart` |

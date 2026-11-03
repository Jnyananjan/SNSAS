# ==============================================================================
# portal.py: MicroPython Captive Portal & Wi-Fi Onboarding Server
# Features:
# 1. Dedicated AP broadcasting on Channel 1 (rock-solid, zero stutter)
# 2. Non-blocking UDP Port 53 Captive DNS Server (triggers OS sign-in popup)
# 3. HTTP 302 probe redirection (Windows NCSI, Android /generate_204, iOS)
# 4. Reliable chunked HTTP sendall with explicit Content-Length
# ==============================================================================

import time
import socket
import network
import machine
import uselect

PORTAL_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Smart Attendance Setup</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #F8FAFC;
      color: #0F172A;
      padding: 24px 16px;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }
    .card {
      background: #FFFFFF;
      max-width: 440px;
      width: 100%;
      border-radius: 16px;
      box-shadow: 0 10px 25px -5px rgba(0,0,0,0.06);
      border: 1px solid #E2E8F0;
      padding: 30px 24px;
    }
    .badge {
      display: inline-block;
      background: #EFF6FF;
      color: #2563EB;
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 12px;
    }
    h1 {
      font-size: 22px;
      font-weight: 700;
      margin-bottom: 6px;
      color: #0F172A;
    }
    p.sub {
      font-size: 14px;
      color: #64748B;
      margin-bottom: 20px;
      line-height: 1.4;
    }
    .field { margin-bottom: 16px; }
    label {
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: #334155;
      margin-bottom: 6px;
    }
    input, select {
      width: 100%;
      padding: 11px 14px;
      border: 1.5px solid #CBD5E1;
      border-radius: 10px;
      font-size: 14px;
      color: #0F172A;
      background: #F8FAFC;
    }
    input:focus, select:focus {
      outline: none;
      background: #FFFFFF;
      border-color: #2563EB;
    }
    button.submit-btn {
      width: 100%;
      background: #2563EB;
      color: #FFFFFF;
      border: none;
      border-radius: 10px;
      padding: 14px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      margin-top: 10px;
    }
    button.submit-btn:hover { background: #1D4ED8; }
    .footer {
      text-align: center;
      margin-top: 20px;
      font-size: 12px;
      color: #94A3B8;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">ESP32-S3 Setup Portal</div>
    <h1>Device Onboarding</h1>
    <p class="sub">Connect this attendance terminal to your local Wi-Fi and Supabase database.</p>
    
    <form method="POST" action="/save">
      <div class="field">
        <label>Wi-Fi Network Name (SSID)</label>
        <select id="wifi-select" onchange="onSelectNetwork(this)" style="margin-bottom: 8px;">
          <option value="">-- Detected Networks ({count} Found) --</option>
          {options}
          <option value="__manual__">&#9997;&#65039; Enter manually / Hidden network...</option>
        </select>
        <input type="text" id="ssid-input" name="ssid" placeholder="Or type SSID manually" required>
      </div>

      <div class="field">
        <label>Wi-Fi Password</label>
        <input type="password" name="password" placeholder="Leave blank if open network">
      </div>

      <div class="field">
        <label>Supabase Project URL</label>
        <input type="url" name="supabase_url" value="{supabase_url}" placeholder="https://xyzproject.supabase.co" required>
      </div>

      <div class="field">
        <label>Supabase Anon Key</label>
        <input type="text" name="supabase_key" value="{supabase_key}" placeholder="eyJhbGciOi..." required>
      </div>

      <div class="field">
        <label>Terminal Device ID</label>
        <input type="text" name="device_id" value="{device_id}" required>
      </div>

      <button type="submit" class="submit-btn">Save &amp; Reboot Terminal</button>
    </form>
    <div class="footer">Smart RFID Attendance System &bull; Open Source</div>
  </div>

  <script>
    function onSelectNetwork(sel) {
      var input = document.getElementById('ssid-input');
      if (sel.value === '__manual__') {
        input.value = '';
        input.focus();
      } else if (sel.value) {
        input.value = sel.value;
      }
    }
  </script>
</body>
</html>
"""

SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Setup Complete</title>
  <style>
    body { font-family: sans-serif; background: #F8FAFC; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 16px; }
    .card { background: white; padding: 36px 24px; border-radius: 16px; text-align: center; max-width: 400px; border: 1px solid #E2E8F0; }
    h2 { color: #059669; margin-bottom: 10px; }
    p { color: #64748B; font-size: 14px; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="card">
    <h2>&#10004; Settings Saved!</h2>
    <p>Terminal is rebooting and connecting to your Wi-Fi network...</p>
    <p>You can now close this window.</p>
  </div>
</body>
</html>
"""

def scan_nearby_networks():
    """Scans for local 2.4 GHz networks, then disables STA to free the radio for AP."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.disconnect()
    time.sleep_ms(300)
    unique = []
    try:
        raw = wlan.scan()
        seen = set()
        for r in raw:
            try:
                s = r[0].decode('utf-8').strip()
            except Exception:
                continue
            if s and s not in seen:
                seen.add(s)
                unique.append((s, r[3]))
        unique.sort(key=lambda x: x[1], reverse=True)
    except Exception as e:
        print("[PORTAL SCAN ERR]:", e)

    # Disable STA after scanning so AP radio has 100% channel stability
    wlan.active(False)
    time.sleep_ms(100)
    return unique

def send_response(cl, status="200 OK", body="", extra_headers=None):
    """Sends complete HTTP response with accurate Content-Length and chunked transmission."""
    body_bytes = body.encode('utf-8') if isinstance(body, str) else body
    header = "HTTP/1.1 " + str(status) + "\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: " + str(len(body_bytes)) + "\r\nConnection: close\r\n"
    if extra_headers:
        for k, v in extra_headers.items():
            header += str(k) + ": " + str(v) + "\r\n"
    header += "\r\n"

    try:
        cl.sendall(header.encode('utf-8'))
        total = len(body_bytes)
        sent = 0
        while sent < total:
            chunk = body_bytes[sent:sent + 1024]
            cl.sendall(chunk)
            sent += len(chunk)
    except Exception as e:
        print("[HTTP SEND ERR]:", e)

def parse_form_data(body):
    """Parses application/x-www-form-urlencoded form data."""
    params = {}
    for part in body.split('&'):
        if '=' in part:
            k, v = part.split('=', 1)
            v = v.replace('+', ' ')
            decoded = []
            i = 0
            while i < len(v):
                if v[i] == '%' and i + 2 < len(v):
                    try:
                        decoded.append(chr(int(v[i+1:i+3], 16)))
                        i += 3
                        continue
                    except Exception:
                        pass
                decoded.append(v[i])
                i += 1
            params[k] = "".join(decoded)
    return params

def save_config(params):
    """Writes updated configuration to config.py on flash."""
    import config
    content = f'''# ==============================================================================
# config.py: MicroPython Configuration for ESP32-S3 Smart Attendance Terminal
# Auto-generated by Setup Portal on {time.time()}
# ==============================================================================

WIFI_SSID = "{params.get('ssid', config.WIFI_SSID)}"
WIFI_PASSWORD = "{params.get('password', '')}"

SUPABASE_URL = "{params.get('supabase_url', config.SUPABASE_URL)}"
SUPABASE_ANON_KEY = "{params.get('supabase_key', config.SUPABASE_ANON_KEY)}"
DEVICE_ID = "{params.get('device_id', config.DEVICE_ID)}"

# Hardware Pins (ESP32-S3 DevKit)
PIN_TFT_SCK  = {config.PIN_TFT_SCK}
PIN_TFT_MOSI = {config.PIN_TFT_MOSI}
PIN_TFT_CS   = {config.PIN_TFT_CS}
PIN_TFT_DC   = {config.PIN_TFT_DC}
PIN_TFT_RST  = {config.PIN_TFT_RST}
PIN_TFT_BL   = {config.PIN_TFT_BL}

PIN_RFID_SCK  = {config.PIN_RFID_SCK}
PIN_RFID_MOSI = {config.PIN_RFID_MOSI}
PIN_RFID_MISO = {config.PIN_RFID_MISO}
PIN_RFID_CS   = {config.PIN_RFID_CS}
PIN_RFID_RST  = {config.PIN_RFID_RST}

PIN_BUZZER = {config.PIN_BUZZER}

SCAN_COOLDOWN_SEC = {config.SCAN_COOLDOWN_SEC}
DISPLAY_HOLD_SEC  = {config.DISPLAY_HOLD_SEC}
'''
    with open('config.py', 'w') as f:
        f.write(content)
    print("[PORTAL] config.py updated successfully.")

def start_portal():
    """Initializes AP and starts non-blocking DNS + HTTP captive portal server."""
    print("\n[PORTAL] Step 1: Scanning nearby Wi-Fi networks...")
    networks = scan_nearby_networks()
    print(f"[PORTAL] Found {len(networks)} networks.")

    print("[PORTAL] Step 2: Starting Access Point 'Smart-Attendance-Setup'...")
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid="Smart-Attendance-Setup", authmode=network.AUTH_OPEN, channel=1)
    ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '192.168.4.1'))

    time.sleep_ms(200)
    print("[PORTAL] Hotspot active at: 192.168.4.1")

    options_html = ""
    for ssid, rssi in networks[:25]:
        strength = "Strong" if rssi >= -65 else ("Med" if rssi >= -78 else "Weak")
        options_html += f'<option value="{ssid}">{ssid} ({rssi} dBm · {strength})</option>\n'

    import config
    html_page = (
        PORTAL_HTML_TEMPLATE
        .replace('{count}', str(len(networks)))
        .replace('{options}', options_html)
        .replace('{supabase_url}', config.SUPABASE_URL)
        .replace('{supabase_key}', config.SUPABASE_ANON_KEY)
        .replace('{device_id}', config.DEVICE_ID)
    )

    # 1. Setup Captive DNS Server on UDP Port 53
    dns_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dns_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    dns_sock.bind(('0.0.0.0', 53))
    dns_sock.setblocking(False)

    # 2. Setup HTTP Server on TCP Port 80
    http_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    http_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    http_sock.bind(('0.0.0.0', 80))
    http_sock.listen(5)
    http_sock.setblocking(False)

    poller = uselect.poll()
    poller.register(dns_sock, uselect.POLLIN)
    poller.register(http_sock, uselect.POLLIN)

    print("[PORTAL] Captive DNS & Web Server running on http://192.168.4.1")

    ap_ip_bytes = b'\xc0\xa8\x04\x01'  # 192.168.4.1

    while True:
        events = poller.poll(200)
        for sock, ev in events:
            # Handle Captive DNS Query (UDP Port 53)
            if sock == dns_sock:
                try:
                    data, addr = dns_sock.recvfrom(256)
                    if data and len(data) > 12:
                        reply = (
                            data[:2] +
                            b'\x81\x80' +
                            data[4:6] + data[4:6] +
                            b'\x00\x00\x00\x00' +
                            data[12:] +
                            b'\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04' +
                            ap_ip_bytes
                        )
                        dns_sock.sendto(reply, addr)
                except Exception:
                    pass

            # Handle HTTP Client Request (TCP Port 80)
            elif sock == http_sock:
                cl = None
                try:
                    cl, addr = http_sock.accept()
                    cl.settimeout(2.0)
                    req = cl.recv(1024).decode('utf-8', 'ignore')
                    if not req:
                        cl.close()
                        continue

                    lines = req.split('\r\n')
                    tokens = lines[0].split(' ')
                    if len(tokens) < 2:
                        cl.close()
                        continue

                    method, path = tokens[0], tokens[1]

                    # Captive portal OS probes (Windows NCSI, Android, Apple) -> 302 Redirect to root
                    is_probe = any(probe in path.lower() for probe in [
                        'connecttest', 'redirect', 'ncsi.txt', 'generate_204',
                        'gen_204', 'hotspot-detect', 'canonical.html'
                    ])
                    # If external domain requested via captive DNS, redirect to 192.168.4.1
                    host_header = ""
                    for l in lines:
                        if l.lower().startswith("host:"):
                            host_header = l.split(":", 1)[1].strip()

                    if is_probe or (host_header and "192.168.4.1" not in host_header):
                        send_response(cl, status="302 Found", body="", extra_headers={"Location": "http://192.168.4.1/"})
                        cl.close()
                        continue

                    # Handle Form Submission POST /save
                    if method == "POST" and path == "/save":
                        content_len = 0
                        for l in lines:
                            if l.lower().startswith('content-length:'):
                                content_len = int(l.split(':')[1].strip())

                        body = req.split('\r\n\r\n', 1)[1] if '\r\n\r\n' in req else ""
                        remaining = content_len - len(body)
                        if remaining > 0:
                            body += cl.recv(remaining).decode('utf-8', 'ignore')

                        params = parse_form_data(body)
                        save_config(params)

                        send_response(cl, status="200 OK", body=SUCCESS_HTML)
                        cl.close()
                        http_sock.close()
                        dns_sock.close()
                        time.sleep(2)
                        print("[PORTAL] Rebooting with new credentials...")
                        machine.reset()
                        return

                    # Default: Serve Setup HTML Form
                    send_response(cl, status="200 OK", body=html_page)
                    cl.close()

                except Exception as e:
                    print("[PORTAL HTTP ERR]:", e)
                    if cl:
                        try:
                            cl.close()
                        except Exception:
                            pass

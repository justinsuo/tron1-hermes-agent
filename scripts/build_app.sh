#!/usr/bin/env bash
# Build ~/Applications/Tron1.app — a clickable macOS app that brings the
# entire stack up (sim + dashboard + auto-push) and opens the dashboard in
# the default browser. No Terminal window shown. Runs silently.
#
# Also places a symlink on the Desktop.
#
# Idempotent — safe to re-run. Overwrites existing Tron1.app.

set -euo pipefail

APP="$HOME/Applications/Tron1.app"
DESKTOP_LINK="$HOME/Desktop/Tron1.app"
VENV="$HOME/.hermes/hermes-agent/venv"
SIM_SCRIPT="$HOME/tron1-sim-mac/sim.py"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# ---------- Info.plist ----------
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>             <string>Tron 1</string>
  <key>CFBundleDisplayName</key>      <string>Tron 1</string>
  <key>CFBundleExecutable</key>       <string>Tron1</string>
  <key>CFBundleIconFile</key>         <string>Tron1</string>
  <key>CFBundleIdentifier</key>       <string>com.justinsuo.tron1</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundlePackageType</key>      <string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key>          <string>1</string>
  <key>LSMinimumSystemVersion</key>   <string>12.0</string>
  <key>LSUIElement</key>              <false/>
  <key>NSHumanReadableCopyright</key> <string>MIT — Tron 1 · Hermes Agent</string>
  <key>NSHighResolutionCapable</key>  <true/>
</dict>
</plist>
PLIST

# ---------- MacOS/Tron1 executable ----------
cat > "$APP/Contents/MacOS/Tron1" <<'SH'
#!/usr/bin/env bash
set -u
VENV="$HOME/.hermes/hermes-agent/venv"
SIM="$HOME/tron1-sim-mac/sim.py"
DASH="$HOME/tron1-sim-mac/dashboard_server.py"
AUTOPUSH_PLIST="$HOME/Library/LaunchAgents/com.justinsuo.tron1-autopush.plist"
URL="http://127.0.0.1:5557/"
LOG="/tmp/tron1-app.log"

notify() { osascript -e "display notification \"$1\" with title \"Tron 1\" sound name \"Tink\"" >/dev/null 2>&1 || true; }
log()    { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
up()     { lsof -i :"$1" 2>/dev/null | grep -q LISTEN; }

{ echo ""; echo "=== $(date) ==="; } >> "$LOG"
notify "Starting sim + dashboard…"
log "launcher start"

up 5556 || { log "starting sim";       nohup "$VENV/bin/python" "$SIM"  > /tmp/tron1-sim.log 2>&1 & disown; }
for _ in {1..20}; do up 5556 && break; sleep 0.3; done

up 5557 || { log "starting dashboard"; nohup "$VENV/bin/python" "$DASH" --port 5557 > /tmp/tron1-dashboard.log 2>&1 & disown; }
for _ in {1..20}; do up 5557 && break; sleep 0.3; done

launchctl list 2>/dev/null | grep -q com.justinsuo.tron1-autopush || \
    { [[ -f "$AUTOPUSH_PLIST" ]] && launchctl load "$AUTOPUSH_PLIST" 2>/dev/null || true; }

if up 5557; then
    log "opening $URL"
    open "$URL"
    notify "Dashboard ready — use Control Panel to start self-play."
else
    notify "Dashboard failed to start. See /tmp/tron1-dashboard.log"
fi
log "launcher done"
exit 0
SH
chmod +x "$APP/Contents/MacOS/Tron1"

# ---------- Icon.icns (generated from a sim render if available) ----------
ICONS_SRC=""
# Try to capture a live render if sim is up
if lsof -i :5556 2>/dev/null | grep -q LISTEN; then
    "$VENV/bin/python" - <<'PY'
import json, socket, base64
s = socket.create_connection(("127.0.0.1", 5556), timeout=5)
s.sendall((json.dumps({"op":"get_image","camera":"tp"})+"\n").encode())
buf = b""
while not buf.endswith(b"\n"):
    c = s.recv(65536); buf += c
    if not c: break
r = json.loads(buf)
if r.get("ok"):
    open("/tmp/icon_src.jpg","wb").write(base64.b64decode(r["data"]["jpeg_base64"]))
PY
    [[ -s /tmp/icon_src.jpg ]] && ICONS_SRC=/tmp/icon_src.jpg
fi

# Pick a Python that has Pillow (Hermes venv is the safe bet)
PYBIN="$VENV/bin/python"
[[ -x "$PYBIN" ]] || PYBIN=python3

# Fallback: a solid-color PNG if no sim available
if [[ -z "$ICONS_SRC" ]]; then
    "$PYBIN" - <<'PY'
from PIL import Image
Image.new("RGB", (1024,1024), (22,28,44)).save("/tmp/icon_src.jpg")
PY
    ICONS_SRC=/tmp/icon_src.jpg
fi

# Compose 1024×1024 rounded-corner icon with label
"$PYBIN" - "$ICONS_SRC" <<'PY'
import sys
from PIL import Image, ImageDraw, ImageFont
src = Image.open(sys.argv[1]).convert("RGBA")
w, h = src.size; side = min(w, h)
src = src.crop(((w-side)//2, (h-side)//2, (w+side)//2, (h+side)//2)).resize((1024,1024), Image.LANCZOS)
mask = Image.new("L", (1024,1024), 0)
ImageDraw.Draw(mask).rounded_rectangle([(40,40),(984,984)], radius=200, fill=255)
out = Image.new("RGBA", (1024,1024), (0,0,0,0))
out.paste(src, (0,0), mask)
overlay = Image.new("RGBA", (1024,1024), (0,0,0,0))
ImageDraw.Draw(overlay).rounded_rectangle([(40,780),(984,984)], radius=200, fill=(15,17,21,220))
out = Image.alpha_composite(out, overlay)
d = ImageDraw.Draw(out)
try:
    font_big   = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 130)
    font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
except OSError:
    font_big = font_small = ImageFont.load_default()
d.text((160,820), "TRON 1", fill=(236,236,243,255), font=font_big)
d.text((160,935), "hermes agent", fill=(130,170,220,255), font=font_small)
out.save("/tmp/icon_1024.png")
PY

ICONSET=/tmp/Tron1.iconset
rm -rf "$ICONSET"; mkdir -p "$ICONSET"
for s in 16 32 64 128 256 512; do
    sips -s format png -z "$s" "$s" /tmp/icon_1024.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    s2=$((s*2))
    sips -s format png -z "$s2" "$s2" /tmp/icon_1024.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
cp /tmp/icon_1024.png "$ICONSET/icon_512x512@2x.png"
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/Tron1.icns"

# ---------- Register with LaunchServices, desktop alias ----------
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "$APP" 2>/dev/null || true
ln -sfn "$APP" "$DESKTOP_LINK"

echo ""
echo "✓ Built $APP"
echo "✓ Symlink placed on Desktop: $DESKTOP_LINK"
echo ""
echo "Double-click Tron 1 on your Desktop (or find it in Launchpad / Spotlight)."

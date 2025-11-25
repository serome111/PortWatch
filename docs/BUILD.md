# Building PortWatch for Distribution

## Quick Build

```bash
./build_app.sh
```

This will:
1. Install Python dependencies
2. Build the frontend (React + Vite)
3. Bundle everything with PyInstaller
4. **Automatically include `terminal-notifier`** in the app bundle
5. Create `dist/PortWatch.app` (macOS) or `dist/portwatch-tray` (Linux)

## What Gets Bundled

The build process includes:
- ✅ Python backend (`server.py`, `alert_engine.py`, etc.)
- ✅ React frontend (compiled to `frontend/dist`)
- ✅ Icons and assets
- ✅ **`terminal-notifier` binary** (macOS only)

## How Terminal-Notifier Bundling Works

### 1. Detection (during build)
`PortWatch.spec` automatically finds `terminal-notifier`:
```python
terminal_notifier_path = shutil.which('terminal-notifier')
binaries_list.append((terminal_notifier_path, '.'))
```

### 2. Runtime Discovery
`notifier.py` searches for the binary in this order:
1. **Bundled location** (`sys._MEIPASS` or `sys.executable.parent`)
2. **System PATH** (`/opt/homebrew/bin/terminal-notifier`)

### 3. Fallback
If `terminal-notifier` is not found, the app uses `osascript` as fallback (requires manual Python notification permissions).

## Distribution

When you distribute `PortWatch.app` to other users:

### ✅ Works Out of the Box
- The app is **fully standalone**
- `terminal-notifier` is bundled inside
- No Homebrew installation required on target machines

### First Run Experience
1. User launches `PortWatch.app`
2. macOS requests sudo password (for network monitoring)
3. User goes to Settings > Alertas > Probar Notificación
4. **macOS asks for notification permission** for `terminal-notifier`
5. User clicks "Allow"
6. Notifications work immediately

## Building Requirements

On your **development machine** (where you run `./build_app.sh`):
- ✅ Homebrew
- ✅ `terminal-notifier` installed: `brew install terminal-notifier`
- ✅ `uv` (Python package manager): https://github.com/astral-sh/uv
- ✅ Node.js / npm (for frontend build)

## Advanced: Manual Build with PyInstaller

```bash
# Option 1: Use the spec file directly
uv run pyinstaller PortWatch.spec

# Option 2: Use the build script with custom platform
./build_app.sh mac      # Force macOS build
./build_app.sh linux    # Force Linux build
```

## Troubleshooting

### "terminal-notifier not found" warning during build
**Cause**: `terminal-notifier` is not installed on your build machine.

**Solution**:
```bash
brew install terminal-notifier
./clean_rebuild.sh  # Rebuild from scratch
```

### Notifications don't work on distributed app
**Cause**: User hasn't granted notification permissions.

**Solution**: 
1. Open `PortWatch.app`
2. Go to Settings > Alertas > Probar Notificación
3. When macOS asks, click "Allow"

### Want to verify the bundle includes terminal-notifier?
```bash
# List all binaries in the app bundle
ls -la dist/PortWatch.app/Contents/MacOS/

# You should see:
# - PortWatch (main executable)
# - terminal-notifier
```

## Clean Rebuild

```bash
./clean_rebuild.sh
```

This removes `build/`, `dist/`, and all PyInstaller cache files, then rebuilds from scratch.

## Code Signing (Optional)

For distribution outside the App Store, you may want to code sign:

```bash
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/PortWatch.app
```

## Notarization (Optional)

For macOS Catalina+, notarization prevents Gatekeeper warnings:

```bash
# 1. Create a zip
ditto -c -k --keepParent dist/PortWatch.app PortWatch.zip

# 2. Submit for notarization
xcrun notarytool submit PortWatch.zip --apple-id your@email.com --password "app-specific-password" --team-id TEAMID

# 3. Staple the ticket
xcrun stapler staple dist/PortWatch.app
```

See: https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution

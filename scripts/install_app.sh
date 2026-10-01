#!/bin/bash
# ==============================================================================
# Install Charlie.app to macOS /Applications
# ==============================================================================

set -e

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
APP_SOURCE="$PROJECT_DIR/Charlie.app"
TARGET_DIR="/Applications"
TARGET_APP="$TARGET_DIR/Charlie.app"

echo "=================================================="
echo "  Installing Charlie.app to $TARGET_DIR"
echo "=================================================="

if [ ! -d "$APP_SOURCE" ]; then
    echo "Error: Could not find $APP_SOURCE"
    exit 1
fi

# Ensure executable permissions on launcher
chmod +x "$APP_SOURCE/Contents/MacOS/Charlie"

# Copy Charlie.app into /Applications
echo "Copying Charlie.app to $TARGET_DIR..."
cp -R "$APP_SOURCE" "$TARGET_DIR/"

# Refresh macOS LaunchServices database
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [ -f "$LSREGISTER" ]; then
    echo "Registering Charlie with LaunchServices..."
    "$LSREGISTER" -f "$TARGET_APP" 2>/dev/null || true
fi

# Touch app bundle to invalidate Finder/Dock icon cache
touch "$TARGET_APP"

echo ""
echo "✅ Success! Charlie.app has been installed to /Applications/Charlie.app"
echo ""
echo "How to use:"
echo "  1. Open Spotlight (Command + Space) and type 'Charlie', then press Enter."
echo "  2. Or open Finder -> Applications -> Double-click 'Charlie'."
echo "  3. Charlie will appear in your top macOS Menu Bar as '⚡ Charlie'."
echo "  4. It listens for 'Hey Charlie' automatically in the background!"
echo "  5. Click '⚡ Charlie' in the menu bar to change voice, push-to-talk, or enable 'Launch at Login'."
echo "=================================================="

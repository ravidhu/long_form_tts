#!/usr/bin/env bash
#
# Build the Electron app for all platforms and publish to GitHub Releases.
#
# Builds macOS natively (must run on a Mac), Linux + Windows via Docker.
#
# Usage:
#   ./scripts/release.sh              # build all platforms
#   ./scripts/release.sh v0.2.0       # explicit version tag
#   ./scripts/release.sh --mac-only   # only build macOS
#   ./scripts/release.sh --linux-only # only build Linux (Docker)
#   ./scripts/release.sh --win-only   # only build Windows (Docker)
#   ./scripts/release.sh --release    # build all platforms + create draft release
#
# Prerequisites:
#   - Node.js + npm
#   - Docker (for Linux and Windows builds)
#   - gh CLI (for publishing): brew install gh && gh auth login

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$APP_DIR/.." && pwd)"

cd "$APP_DIR"

# --- Parse args ---
PUBLISH=false
BUILD_MAC=true
BUILD_LINUX=true
BUILD_WIN=true
TAG=""

for arg in "$@"; do
  case "$arg" in
    --release)     PUBLISH=true ;;
    --mac-only)    BUILD_LINUX=false; BUILD_WIN=false ;;
    --linux-only)  BUILD_MAC=false; BUILD_WIN=false ;;
    --win-only)    BUILD_MAC=false; BUILD_LINUX=false ;;
    v*)            TAG="$arg" ;;
    *)             echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

# Default tag from package.json version
if [ -z "$TAG" ]; then
  VERSION=$(node -p "require('./package.json').version")
  TAG="v$VERSION"
fi

echo "=== Long Form TTS Release Builder ==="
echo "Tag: $TAG"
echo "Build macOS: $BUILD_MAC | Linux: $BUILD_LINUX | Windows: $BUILD_WIN"
echo ""

# --- Helper: download uv binary ---
download_uv() {
  local platform="$1" arch="$2"
  local dir="resources/bin/$platform/$arch"
  mkdir -p "$dir"

  local bin="$dir/uv"
  [ "$platform" = "win" ] && bin="$dir/uv.exe"

  if [ -f "$bin" ]; then
    echo "  uv binary already exists: $bin"
    return
  fi

  echo "  Downloading uv for $platform/$arch..."
  case "$platform/$arch" in
    mac/arm64)
      curl -fsSL https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz | tar xz -C /tmp
      cp /tmp/uv-aarch64-apple-darwin/uv "$bin" ;;
    mac/x64)
      curl -fsSL https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-apple-darwin.tar.gz | tar xz -C /tmp
      cp /tmp/uv-x86_64-apple-darwin/uv "$bin" ;;
    linux/x64)
      curl -fsSL https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz | tar xz -C /tmp
      cp /tmp/uv-x86_64-unknown-linux-gnu/uv "$bin" ;;
    win/x64)
      curl -fsSL -o /tmp/uv-win.zip https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip
      unzip -o /tmp/uv-win.zip -d /tmp/uv-win
      cp /tmp/uv-win/uv.exe "$bin" ;;
    *)
      echo "  ERROR: No uv download for $platform/$arch"; return 1 ;;
  esac
  chmod +x "$bin" 2>/dev/null || true
}

# --- Collect all artifacts here ---
RELEASE_DIR="$APP_DIR/release"
mkdir -p "$RELEASE_DIR"

# ============================================================
# macOS — native build (arm64 + x64)
# ============================================================
if [ "$BUILD_MAC" = true ]; then
  echo "--- Building macOS (native) ---"

  download_uv mac arm64
  download_uv mac x64

  npm ci --silent
  npx electron-vite build
  npx electron-builder --mac --arm64 --x64 --publish never

  echo "  macOS build complete."
  echo ""
fi

# ============================================================
# Linux — Docker build
# ============================================================
if [ "$BUILD_LINUX" = true ]; then
  echo "--- Building Linux (Docker) ---"

  if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker is required for Linux builds. Install Docker Desktop."
    exit 1
  fi

  download_uv linux x64

  # Build vite output on host first (faster, avoids node_modules in container)
  npm ci --silent
  npx electron-vite build

  # Run electron-builder inside Docker
  docker run --rm \
    -v "$APP_DIR":/app \
    -v "$PROJECT_ROOT/scripts":/project-scripts:ro \
    -v "$PROJECT_ROOT/src":/project-src:ro \
    -v "$PROJECT_ROOT/pyproject.toml":/project-pyproject.toml:ro \
    -v "$PROJECT_ROOT/uv.lock":/project-uv.lock:ro \
    -v "$APP_DIR/release":/app/release \
    -w /app \
    electronuserland/builder:20 \
    bash -c "
      npm ci --silent 2>/dev/null
      npx electron-builder --linux --x64 --publish never
    "

  echo "  Linux build complete."
  echo ""
fi

# ============================================================
# Windows — Docker build (Wine cross-compilation)
# ============================================================
if [ "$BUILD_WIN" = true ]; then
  echo "--- Building Windows (Docker + Wine) ---"

  if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker is required for Windows builds. Install Docker Desktop."
    exit 1
  fi

  download_uv win x64

  # Build vite output on host first
  npm ci --silent
  npx electron-vite build

  # Run electron-builder with Wine inside Docker
  docker run --rm \
    -v "$APP_DIR":/app \
    -v "$PROJECT_ROOT/scripts":/project-scripts:ro \
    -v "$PROJECT_ROOT/src":/project-src:ro \
    -v "$PROJECT_ROOT/pyproject.toml":/project-pyproject.toml:ro \
    -v "$PROJECT_ROOT/uv.lock":/project-uv.lock:ro \
    -v "$APP_DIR/release":/app/release \
    -w /app \
    electronuserland/builder:wine \
    bash -c "
      npm ci --silent 2>/dev/null
      npx electron-builder --win --x64 --publish never
    "

  echo "  Windows build complete."
  echo ""
fi

# --- List all artifacts ---
echo "=== Build Artifacts ==="
find "$RELEASE_DIR" -maxdepth 1 -type f \( \
  -name "*.dmg" -o -name "*.AppImage" -o -name "*.deb" \
  -o -name "*.exe" -o -name "*.zip" -o -name "*.tar.gz" \
\) 2>/dev/null | sort | while read -r f; do
  name="$(basename "$f")"
  size="$(du -h "$f" | cut -f1)"
  case "$name" in
    *.dmg)      desc="macOS installer (drag-to-Applications disk image)" ;;
    *.zip)
      if echo "$name" | grep -qi "darwin\|mac"; then
        desc="macOS portable archive (unzip and run, no install needed)"
      elif echo "$name" | grep -qi "win"; then
        desc="Windows portable archive (unzip and run, no install needed)"
      else
        desc="Portable archive (unzip and run)"
      fi ;;
    *.AppImage) desc="Linux portable app (chmod +x and run, no install needed)" ;;
    *.deb)      desc="Debian/Ubuntu installer (install via dpkg -i or apt)" ;;
    *.exe)      desc="Windows installer (double-click to install)" ;;
    *.tar.gz)   desc="Linux portable archive (extract and run)" ;;
    *)          desc="" ;;
  esac
  echo "  $name  ($size)  — $desc"
done
echo ""

if [ "$PUBLISH" != true ]; then
  echo "Build complete. Artifacts in app/release/"
  echo "To publish, re-run with --release"
  exit 0
fi

# ============================================================
# Publish to GitHub Releases
# ============================================================
if ! command -v gh &>/dev/null; then
  echo "ERROR: 'gh' CLI not found. Install it to publish releases:"
  echo "  brew install gh     # macOS"
  echo "  sudo apt install gh # Linux"
  echo ""
  echo "Then run: gh auth login"
  echo "Or use --build-only to skip publishing."
  exit 1
fi

echo "=== Publishing to GitHub Releases as $TAG (draft) ==="

# Collect release files
RELEASE_FILES=()
while IFS= read -r f; do
  RELEASE_FILES+=("$f")
done < <(find "$RELEASE_DIR" -maxdepth 1 -type f \( \
  -name "*.dmg" -o -name "*.AppImage" -o -name "*.deb" \
  -o -name "*.exe" -o -name "*.zip" -o -name "*.tar.gz" \
\))

if [ ${#RELEASE_FILES[@]} -eq 0 ]; then
  echo "No release artifacts found!"
  exit 1
fi

# Create tag if it doesn't exist
cd "$PROJECT_ROOT"
if ! git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Creating tag $TAG..."
  git tag "$TAG"
  git push origin "$TAG"
fi

# Create or update the release
if gh release view "$TAG" >/dev/null 2>&1; then
  echo "Release $TAG exists, uploading artifacts..."
  gh release upload "$TAG" "${RELEASE_FILES[@]}" --clobber
else
  echo "Creating draft release $TAG..."
  gh release create "$TAG" "${RELEASE_FILES[@]}" \
    --draft \
    --title "$TAG" \
    --generate-notes
fi

echo ""
echo "Done! Release URL:"
gh release view "$TAG" --json url -q .url

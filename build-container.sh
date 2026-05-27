#!/usr/bin/env bash
# Build the pi-less-yolo container image.
#
# The little-coder fork lives at vendor/little-coder/ inside this repo.
# To update it: cd vendor/little-coder && git pull
# Then rebuild: ./build-container.sh
#
# Usage:
#   ./build-container.sh          # build with whatever's in vendor/little-coder/
#   ./build-container.sh --force  # force rebuild even if image exists

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENDOR_DIR="${REPO_ROOT}/vendor/little-coder"
DOCKER_CMD="${PI_CONTAINER_RUNTIME:-docker}"

# Verify the fork is present
if [[ ! -d "${VENDOR_DIR}" ]] || [[ ! -f "${VENDOR_DIR}/package.json" ]]; then
  echo "error: vendor/little-coder/ not found" >&2
  echo "Set up your fork:" >&2
  echo "  git clone https://github.com/k0valik/little-coder ${VENDOR_DIR}" >&2
  exit 1
fi

VERSION=$(node -e "console.log(require('${VENDOR_DIR}/package.json').version)" 2>/dev/null || echo "unknown")
echo "Building with little-coder v${VERSION} from vendor/little-coder/"
echo ""

# Build
BUILD_ARGS=()
[[ "${1:-}" == "--force" ]] && BUILD_ARGS+=(--no-cache)
# --network=host is needed on Linux (DNS workaround for systemd-resolved).
# macOS Docker Desktop handles DNS natively; skip it.
[[ "$(uname -s)" == "Linux" ]] && BUILD_ARGS+=(--network=host)

"${DOCKER_CMD}" build "${BUILD_ARGS[@]}" \
  -f "${REPO_ROOT}/Dockerfile" \
  -t "pi-less-yolo:latest" \
  "${REPO_ROOT}"

echo ""
echo "Image 'pi-less-yolo:latest' built successfully."
echo ""
echo "Run: mise run pi"
echo ""
echo "To update your fork: cd vendor/little-coder && git pull"

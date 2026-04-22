#!/usr/bin/env bash
# Deploy the sidecar into the Ubuntu VM and start it.
# Assumes the VM is reachable on ssh port 2222 (per ~/tron1_vm default).

set -euo pipefail

VM_HOST="${VM_HOST:-localhost}"
VM_PORT="${VM_PORT:-2222}"
VM_USER="${VM_USER:-justin}"
SIDECAR_PORT="${SIDECAR_PORT:-5556}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[deploy] copying sidecar.py to ${VM_USER}@${VM_HOST}:~/hermes_sidecar.py ..."
scp -P "$VM_PORT" -o StrictHostKeyChecking=no \
    "${SCRIPT_DIR}/sidecar.py" \
    "${VM_USER}@${VM_HOST}:~/hermes_sidecar.py"

echo "[deploy] starting sidecar in a detached screen on the VM ..."
ssh -p "$VM_PORT" -o StrictHostKeyChecking=no "${VM_USER}@${VM_HOST}" \
    "screen -dmS hermes_sidecar bash -lc '\
        source /opt/ros/humble/setup.bash; \
        [ -f \"$HOME/tron1_ws/install/setup.bash\" ] && source \"$HOME/tron1_ws/install/setup.bash\"; \
        python3 ~/hermes_sidecar.py --host 0.0.0.0 --port ${SIDECAR_PORT} -v \
            >> ~/hermes_sidecar.log 2>&1'"

echo "[deploy] done. To port-forward onto the Mac, run:"
echo "  ssh -N -L ${SIDECAR_PORT}:localhost:${SIDECAR_PORT} -p ${VM_PORT} ${VM_USER}@${VM_HOST}"
echo ""
echo "Then on Mac: export HERMES_ROS2_HOST=127.0.0.1 HERMES_ROS2_PORT=${SIDECAR_PORT}"

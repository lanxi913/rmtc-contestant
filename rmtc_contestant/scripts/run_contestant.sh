#!/usr/bin/env bash
# Usage: RMTC_STAGE=1 TEAM=A TEAM_NAME='队名' bash scripts/run_contestant.sh
# Stage 2 additionally needs AI_GATEWAY, RMTC_TEAM_TOKEN and AI_MODEL.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
export RMTC_STAGE="${RMTC_STAGE:-1}"
export TEAM="${TEAM:-A}"
export TEAM_NAME="${TEAM_NAME:-RMTC contestant}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
case "$RMTC_STAGE" in 1|2) ;; *) echo 'RMTC_STAGE must be 1 or 2' >&2; exit 2 ;; esac
case "$TEAM" in A|B|C|D) ;; *) echo 'TEAM must be A, B, C or D' >&2; exit 2 ;; esac
if [[ "$RMTC_STAGE" == 2 ]]; then
  : "${AI_GATEWAY:?Set AI_GATEWAY for stage 2}"
  : "${RMTC_TEAM_TOKEN:?Set RMTC_TEAM_TOKEN for stage 2}"
  : "${AI_MODEL:?Set AI_MODEL for stage 2}"
  export AI_GATEWAY RMTC_TEAM_TOKEN AI_MODEL
fi
# ROS setup scripts may refer to unset shell variables.
set +u
source "${ROS_SETUP:-/opt/ros/humble/setup.bash}"
if [[ -n "${RMTC_WORKSPACE_SETUP:-}" ]]; then
  source "$RMTC_WORKSPACE_SETUP"
elif [[ -f "${PACKAGE_ROOT}/../install/setup.bash" ]]; then
  source "${PACKAGE_ROOT}/../install/setup.bash"
fi
set -u
export PYTHONPATH="${PACKAGE_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 -m rmtc_contestant.node "$@"

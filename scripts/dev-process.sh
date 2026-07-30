#!/usr/bin/env bash
#
# Run a long-running dev process (dev server, task worker, frontend watcher) in
# the background instead of blocking the current shell.
#
# Every subcommand returns promptly, which makes these processes safe to start
# from non-interactive sessions (CI, scripts, coding agents).
#
# Usage:
#   scripts/dev-process.sh start <name> <ready-spec> <command> [args...]
#   scripts/dev-process.sh stop <name>
#   scripts/dev-process.sh status <name>
#   scripts/dev-process.sh logs <name> [lines]
#
# Ready specs (how "started successfully" is determined):
#   http://127.0.0.1:8000/   wait until the URL answers
#   log:<pattern>            wait until the log matches the extended regex
#   -                        only wait until the process survives the settle time
#
# State lives in tmp/<name>.pid and tmp/<name>.log (tmp/ is gitignored).
# Override the readiness timeout with LD_DEV_TIMEOUT (seconds).

set -uo pipefail

RUN_DIR="${LD_DEV_RUN_DIR:-tmp}"
TIMEOUT="${LD_DEV_TIMEOUT:-60}"
SETTLE_SECONDS=2

usage() {
  sed -n '3,25p' "$0" | sed 's/^# \{0,1\}//'
}

pid_file() { echo "$RUN_DIR/$1.pid"; }
log_file() { echo "$RUN_DIR/$1.log"; }

# Echoes the recorded pid if the process is still alive, otherwise nothing.
running_pid() {
  local file
  file="$(pid_file "$1")"
  [ -f "$file" ] || return 1
  local pid
  pid="$(cat "$file" 2>/dev/null)"
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  echo "$pid"
}

http_ok() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    # No -f: any HTTP response means the server is accepting connections.
    curl -s -o /dev/null --max-time 2 "$url"
    return $?
  fi
  # Fallback: plain TCP connect via bash.
  local host_port="${url#*://}"
  host_port="${host_port%%/*}"
  local host="${host_port%%:*}"
  local port="${host_port##*:}"
  [ "$port" = "$host" ] && port=80
  (exec 3<>"/dev/tcp/$host/$port") 2>/dev/null
}

is_ready() {
  local spec="$1" name="$2"
  case "$spec" in
    -|"") return 0 ;;
    log:*) grep -Eq -- "${spec#log:}" "$(log_file "$name")" 2>/dev/null ;;
    http://*|https://*) http_ok "$spec" ;;
    *)
      echo "error: unsupported ready spec '$spec'" >&2
      exit 2
      ;;
  esac
}

tail_log() {
  local name="$1" lines="${2:-40}"
  local file
  file="$(log_file "$name")"
  if [ -f "$file" ]; then
    echo "--- last $lines lines of $file ---"
    tail -n "$lines" "$file"
  fi
}

cmd_start() {
  local name="${1:-}" ready="${2:-}"
  shift 2 2>/dev/null || { usage >&2; exit 2; }
  if [ -z "$name" ] || [ "$#" -eq 0 ]; then
    usage >&2
    exit 2
  fi

  local existing
  if existing="$(running_pid "$name")"; then
    echo "$name already running (pid $existing); logs: $(log_file "$name")"
    return 0
  fi

  mkdir -p "$RUN_DIR"
  local log
  log="$(log_file "$name")"
  : >"$log"

  # Python block-buffers stdout when it is a file rather than a tty, which
  # would hide the startup banner and request log until the buffer fills.
  # Harmless for non-Python processes.
  export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"

  # Job control gives the child its own process group, so stop can signal the
  # whole tree (e.g. Django's autoreloader parent plus its worker).
  set -m
  nohup "$@" >>"$log" 2>&1 &
  local pid=$!
  set +m
  echo "$pid" >"$(pid_file "$name")"

  local waited=0
  local settled=0
  while [ "$waited" -lt "$TIMEOUT" ]; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "error: $name exited during startup" >&2
      tail_log "$name" >&2
      rm -f "$(pid_file "$name")"
      return 1
    fi
    if [ "$settled" -ge "$SETTLE_SECONDS" ] && is_ready "$ready" "$name"; then
      echo "$name started (pid $pid); logs: $log"
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
    settled=$((settled + 1))
  done

  echo "error: $name did not become ready within ${TIMEOUT}s" >&2
  tail_log "$name" >&2
  return 1
}

cmd_stop() {
  local name="${1:?name required}"
  local pid
  if ! pid="$(running_pid "$name")"; then
    echo "$name is not running"
    rm -f "$(pid_file "$name")"
    return 0
  fi

  # Negative pid targets the whole process group; fall back to the single pid.
  kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null

  local waited=0
  while [ "$waited" -lt 10 ] && kill -0 "$pid" 2>/dev/null; do
    sleep 1
    waited=$((waited + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null
  fi

  rm -f "$(pid_file "$name")"
  echo "$name stopped"
}

cmd_status() {
  local name="${1:?name required}"
  local pid
  if pid="$(running_pid "$name")"; then
    echo "$name running (pid $pid); logs: $(log_file "$name")"
    return 0
  fi
  echo "$name not running"
  return 1
}

cmd_logs() {
  local name="${1:?name required}"
  tail_log "$name" "${2:-100}"
}

case "${1:-}" in
  start) shift; cmd_start "$@" ;;
  stop) shift; cmd_stop "$@" ;;
  status) shift; cmd_status "$@" ;;
  logs) shift; cmd_logs "$@" ;;
  ""|-h|--help|help) usage ;;
  *)
    echo "error: unknown subcommand '$1'" >&2
    usage >&2
    exit 2
    ;;
esac

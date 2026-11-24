#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  sudo -A ./scripts/netboot/start_dnsmasq.sh \
    --interface <nic> \
    --dhcp-range <start,end,lease> \
    --tftp-root <dir> \
    [--bind-address <ip>]

Environment defaults (optional):
  RECOVERY_BMC_NETBOOT_INTERFACE
  RECOVERY_BMC_NETBOOT_DHCP_RANGE
  RECOVERY_BMC_TFTP_ROOT
  RECOVERY_BMC_NETBOOT_BIND_ADDRESS

Example:
  sudo -A ./scripts/netboot/start_dnsmasq.sh \
    --interface enx001122334455 \
    --dhcp-range 192.168.88.50,192.168.88.150,12h \
    --tftp-root ./scripts/netboot/tftp-root \
    --bind-address 192.168.88.1
EOF
}

INTERFACE="${RECOVERY_BMC_NETBOOT_INTERFACE:-}"
DHCP_RANGE="${RECOVERY_BMC_NETBOOT_DHCP_RANGE:-}"
TFTP_ROOT="${RECOVERY_BMC_TFTP_ROOT:-}"
BIND_ADDRESS="${RECOVERY_BMC_NETBOOT_BIND_ADDRESS:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interface)
      INTERFACE="${2:-}"
      shift 2
      ;;
    --dhcp-range)
      DHCP_RANGE="${2:-}"
      shift 2
      ;;
    --tftp-root)
      TFTP_ROOT="${2:-}"
      shift 2
      ;;
    --bind-address)
      BIND_ADDRESS="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$INTERFACE" || -z "$DHCP_RANGE" || -z "$TFTP_ROOT" ]]; then
  echo "Missing required arguments." >&2
  usage
  exit 2
fi

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root (use: sudo -A ...)." >&2
  exit 1
fi

if ! command -v dnsmasq >/dev/null 2>&1; then
  echo "dnsmasq not found. Install it first (e.g. apt install dnsmasq)." >&2
  exit 1
fi

TFTP_ROOT_ABS="$(realpath "$TFTP_ROOT")"
mkdir -p "$TFTP_ROOT_ABS"

RUNTIME_DIR="${TMPDIR:-/tmp}/recovery-bmc-netboot"
mkdir -p "$RUNTIME_DIR"
CONF_FILE="$RUNTIME_DIR/dnsmasq.conf"
PID_FILE="$RUNTIME_DIR/dnsmasq.pid"
LEASE_FILE="$RUNTIME_DIR/dnsmasq.leases"

cat >"$CONF_FILE" <<EOF
port=0
interface=${INTERFACE}
bind-interfaces
dhcp-range=${DHCP_RANGE}
dhcp-authoritative
log-dhcp
enable-tftp
tftp-root=${TFTP_ROOT_ABS}
dhcp-leasefile=${LEASE_FILE}
pid-file=${PID_FILE}
EOF

if [[ -n "$BIND_ADDRESS" ]]; then
  cat >>"$CONF_FILE" <<EOF
listen-address=${BIND_ADDRESS}
EOF
fi

echo "[recovery-bmc] dnsmasq config: $CONF_FILE"
echo "[recovery-bmc] tftp root:      $TFTP_ROOT_ABS"
echo "[recovery-bmc] stop command:   sudo -A kill \$(cat '$PID_FILE')"

exec dnsmasq --keep-in-foreground --conf-file="$CONF_FILE"

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start dnsmasq for recovery-bmc netboot.")
    parser.add_argument(
        "--interface",
        default=os.environ.get("RECOVERY_BMC_NETBOOT_INTERFACE", ""),
    )
    parser.add_argument(
        "--dhcp-range",
        default=os.environ.get("RECOVERY_BMC_NETBOOT_DHCP_RANGE", ""),
    )
    parser.add_argument(
        "--tftp-root",
        default=os.environ.get("RECOVERY_BMC_TFTP_ROOT", ""),
    )
    parser.add_argument(
        "--bind-address",
        default=os.environ.get("RECOVERY_BMC_NETBOOT_BIND_ADDRESS", ""),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if os.geteuid() != 0:
        print("Run as root (use: sudo -A ...).", file=sys.stderr)
        return 1

    if not args.interface or not args.dhcp_range or not args.tftp_root:
        print(
            "Missing required settings. Provide --interface/--dhcp-range/--tftp-root "
            "or set RECOVERY_BMC_NETBOOT_INTERFACE/RECOVERY_BMC_NETBOOT_DHCP_RANGE/"
            "RECOVERY_BMC_TFTP_ROOT.",
            file=sys.stderr,
        )
        return 2

    tftp_root = Path(args.tftp_root).expanduser().resolve()
    tftp_root.mkdir(parents=True, exist_ok=True)

    runtime_dir = Path(os.environ.get("TMPDIR", "/tmp")) / "recovery-bmc-netboot"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    conf_file = runtime_dir / "dnsmasq.conf"
    pid_file = runtime_dir / "dnsmasq.pid"
    lease_file = runtime_dir / "dnsmasq.leases"

    lines = [
        "port=0",
        f"interface={args.interface}",
        "bind-interfaces",
        f"dhcp-range={args.dhcp_range}",
        "dhcp-authoritative",
        "log-dhcp",
        "enable-tftp",
        f"tftp-root={tftp_root}",
        f"dhcp-leasefile={lease_file}",
        f"pid-file={pid_file}",
    ]
    if args.bind_address:
        lines.append(f"listen-address={args.bind_address}")
    conf_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[recovery-bmc] dnsmasq config: {conf_file}")
    print(f"[recovery-bmc] tftp root:      {tftp_root}")
    print(f"[recovery-bmc] stop command:   sudo -A kill $(cat '{pid_file}')")

    if args.dry_run:
        return 0

    if not shutil.which("dnsmasq"):
        print("dnsmasq not found. Install it first (e.g. apt install dnsmasq).", file=sys.stderr)
        return 1

    os.execvp("dnsmasq", ["dnsmasq", "--keep-in-foreground", f"--conf-file={conf_file}"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

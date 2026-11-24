from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

import usb.core

from .agent import RecoveryAgent
from .errors import RecoveryError
from .models import RecoveryImages
from .protocol import RecoveryTransport
from .transports import I3cTransport, PyUsbTransport

DEFAULT_USB_VENDOR_ID = 0x0424
DEFAULT_USB_PRODUCT_ID = 0x0007
DEFAULT_I3C_CLK_KHZ = 12500
DEFAULT_I3C_ENTDAA_ADDR = 0x08
DEFAULT_TRANSPORT = "usb"
DEFAULT_POLL_INTERVAL = 0.01
DEFAULT_STATE_TIMEOUT = 30.0
DEFAULT_DISCOVERY_TIMEOUT = 10.0
DEFAULT_TRANSFER_TIMEOUT = 10.0
_DOTENV_LOADED = False


def _load_dotenv_into_env() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    candidates = []
    override = os.environ.get("RECOVERY_BMC_DOTENV", "").strip()
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(Path.cwd() / ".env")
    candidates.append(Path(__file__).resolve().parents[3] / ".env")

    seen: set[Path] = set()
    for dotenv_path in candidates:
        if dotenv_path in seen:
            continue
        seen.add(dotenv_path)
        if not dotenv_path.exists():
            continue
        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
        break
    _DOTENV_LOADED = True


def _env_or_default(name: str, default):
    _load_dotenv_into_env()
    return os.environ.get(name, default)


def parse_usb_id(value: str) -> int:
    try:
        usb_id = int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid USB ID: {value}") from error
    if not 0 <= usb_id <= 0xFFFF:
        raise argparse.ArgumentTypeError("USB ID must fit in 16 bits")
    return usb_id


def parse_i3c_addr(value: str) -> int:
    try:
        addr = int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid I3C address: {value}") from error
    if not 0 <= addr <= 0x7F:
        raise argparse.ArgumentTypeError("I3C address must be 7-bit")
    return addr


def build_argument_parser() -> argparse.ArgumentParser:
    caliptra_fmc_rt = _env_or_default("RECOVERY_BMC_CALIPTRA_FMC_RT", None)
    soc_manifest = _env_or_default("RECOVERY_BMC_SOC_MANIFEST", None)
    mcu_runtime = _env_or_default("RECOVERY_BMC_MCU_RUNTIME", None)
    app_core_images_env = _env_or_default("RECOVERY_BMC_APP_CORE_IMAGES", "")
    app_core_defaults = [
        Path(p.strip()) for p in app_core_images_env.split(",") if p.strip()
    ]
    i3c_addr_env = _env_or_default("RECOVERY_BMC_I3C_ADDR", "")
    parser = argparse.ArgumentParser(description="Unified OCP Recovery agent over USB or I3C.")
    parser.add_argument(
        "--transport",
        choices=["usb", "i3c"],
        default=_env_or_default("RECOVERY_BMC_TRANSPORT", DEFAULT_TRANSPORT),
    )
    parser.add_argument("--probe", action="store_true")
    parser.add_argument(
        "--caliptra-fmc-rt",
        type=Path,
        default=Path(caliptra_fmc_rt) if caliptra_fmc_rt else None,
    )
    parser.add_argument(
        "--soc-manifest",
        type=Path,
        default=Path(soc_manifest) if soc_manifest else None,
    )
    parser.add_argument(
        "--mcu-runtime",
        type=Path,
        default=Path(mcu_runtime) if mcu_runtime else None,
    )
    parser.add_argument(
        "--app-image",
        type=Path,
        action="append",
        default=app_core_defaults,
        help="Additional app image path (repeatable, mapped to image_index 3,4,5...)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(_env_or_default("RECOVERY_BMC_POLL_INTERVAL", DEFAULT_POLL_INTERVAL)),
    )
    parser.add_argument(
        "--state-timeout",
        type=float,
        default=float(_env_or_default("RECOVERY_BMC_STATE_TIMEOUT", DEFAULT_STATE_TIMEOUT)),
    )
    parser.add_argument(
        "--vendor-id",
        type=parse_usb_id,
        default=parse_usb_id(
            str(_env_or_default("RECOVERY_BMC_USB_VENDOR_ID", hex(DEFAULT_USB_VENDOR_ID)))
        ),
    )
    parser.add_argument(
        "--product-id",
        type=parse_usb_id,
        default=parse_usb_id(
            str(_env_or_default("RECOVERY_BMC_USB_PRODUCT_ID", hex(DEFAULT_USB_PRODUCT_ID)))
        ),
    )
    parser.add_argument(
        "--discovery-timeout",
        type=float,
        default=float(
            _env_or_default("RECOVERY_BMC_DISCOVERY_TIMEOUT", DEFAULT_DISCOVERY_TIMEOUT)
        ),
    )
    parser.add_argument(
        "--transfer-timeout",
        type=float,
        default=float(_env_or_default("RECOVERY_BMC_TRANSFER_TIMEOUT", DEFAULT_TRANSFER_TIMEOUT)),
    )
    parser.add_argument("--uart", type=str, default=_env_or_default("RECOVERY_BMC_I3C_UART", None))
    parser.add_argument(
        "--clk-khz",
        type=int,
        default=int(_env_or_default("RECOVERY_BMC_I3C_CLK_KHZ", DEFAULT_I3C_CLK_KHZ)),
    )
    parser.add_argument(
        "--addr",
        type=parse_i3c_addr,
        default=parse_i3c_addr(i3c_addr_env) if i3c_addr_env else None,
    )
    parser.add_argument(
        "--entdaa-addr",
        type=parse_i3c_addr,
        default=parse_i3c_addr(
            str(_env_or_default("RECOVERY_BMC_I3C_ENTDAA_ADDR", hex(DEFAULT_I3C_ENTDAA_ADDR)))
        ),
    )
    return parser


def _open_transport(args) -> RecoveryTransport:
    if args.transport == "usb":
        return PyUsbTransport.open(
            args.vendor_id,
            args.product_id,
            args.discovery_timeout,
            args.transfer_timeout,
        )
    return I3cTransport.open(args.uart, args.clk_khz, args.addr, args.entdaa_addr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    image_paths = (args.caliptra_fmc_rt, args.soc_manifest, args.mcu_runtime)
    if not args.probe and any(path is None for path in image_paths):
        parser.error(
            "--caliptra-fmc-rt, --soc-manifest, and --mcu-runtime are required "
            "unless --probe is used"
        )

    transport = None
    try:
        transport = _open_transport(args)
        agent = RecoveryAgent(
            transport,
            poll_interval=args.poll_interval,
            state_timeout=args.state_timeout,
        )
        if args.probe:
            agent.probe()
            return 0

        images = RecoveryImages(
            caliptra_fmc_rt=args.caliptra_fmc_rt.read_bytes(),
            soc_manifest=args.soc_manifest.read_bytes(),
            mcu_runtime=args.mcu_runtime.read_bytes(),
            app_core_images=tuple(path.read_bytes() for path in args.app_core_image),
        )
        agent.run(images)
        return 0
    except (OSError, RecoveryError, usb.core.USBError) as error:
        print(f"recovery-bmc: error: {error}", file=sys.stderr)
        return 1
    finally:
        if transport is not None:
            transport.close()

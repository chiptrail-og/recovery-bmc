# recovery-bmc

Unified BMC-side OCP Recovery agent with two transports:

- `--transport usb`: OCP over USB control transfers
- `--transport i3c`: OCP over I3C private transfers

Configuration values can be provided by:
1. CLI arguments (highest priority)
2. OS environment variables (`RECOVERY_BMC_*`)
3. `.env` file (`RECOVERY_BMC_DOTENV` override, then `./.env`)

## Setup

Clone with submodules:

```bash
git clone --recurse-submodules https://github.com/chiptrail-og/recovery-bmc.git
```

If already cloned:

```bash
git submodule update --init --recursive
```

Install with uv:

```bash
uv sync --all-groups
```

## USB mode

Probe:

```bash
uv run recovery-bmc --transport usb --probe
```

Cross-platform USB env examples:

- Windows:
  - `set RECOVERY_BMC_USB_VENDOR_ID=0x0424`
  - `set RECOVERY_BMC_USB_PRODUCT_ID=0x0007`
- Linux/macOS:
  - `export RECOVERY_BMC_USB_VENDOR_ID=0x0424`
  - `export RECOVERY_BMC_USB_PRODUCT_ID=0x0007`

Recover:

```bash
uv run recovery-bmc --transport usb \
  --caliptra-fmc-rt caliptra.bin \
  --soc-manifest manifest.bin \
  --mcu-runtime mcu.bin \
  --app-image app0.bin \
  --app-image app1.bin
```

`--app-image` is optional and repeatable. It maps by order to recovery
`image_index` 3, 4, 5, ...

Single-image shorthand (legacy-style):

```bash
uv run recovery-bmc --transport usb firmware.bin --no-activate
```

## I3C mode

I3C transport follows a generic import path: it first uses normal Python
module resolution (`import i3cblaster`). If not found, it falls back to
`I3CBlaster/python` (submodule source), and you can override with
`RECOVERY_BMC_I3CBLASTER_PYTHON`.

Probe:

```bash
uv run recovery-bmc --transport i3c --probe --uart COM5
```

Cross-platform UART examples:

- Windows: `set RECOVERY_BMC_I3C_UART=COM5`
- Linux/macOS: `export RECOVERY_BMC_I3C_UART=/dev/ttyACM0`

Legacy env `I3C_BLASTER_UART` is also supported for compatibility.

Recover:

```bash
uv run recovery-bmc --transport i3c \
  --uart COM5 \
  --caliptra-fmc-rt caliptra.bin \
  --soc-manifest manifest.bin \
  --mcu-runtime mcu.bin
```

Common options migrated from i3cblaster-bmc:

- `--chunk-size`
- `--no-activate`
- `--log-level`
- `--debug`

These options are shared by both transports (USB and I3C), not I3C-only.

### Supported environment variables

- `RECOVERY_BMC_TRANSPORT` (`usb` or `i3c`)
- `RECOVERY_BMC_USB_VENDOR_ID`, `RECOVERY_BMC_USB_PRODUCT_ID`
- `RECOVERY_BMC_DISCOVERY_TIMEOUT`, `RECOVERY_BMC_TRANSFER_TIMEOUT`
- `RECOVERY_BMC_I3C_UART`, `RECOVERY_BMC_I3C_CLK_KHZ`
- `I3C_BLASTER_UART` (legacy alias for `RECOVERY_BMC_I3C_UART`)
- `RECOVERY_BMC_I3C_ADDR`, `RECOVERY_BMC_I3C_ENTDAA_ADDR`
- `RECOVERY_BMC_POLL_INTERVAL`, `RECOVERY_BMC_STATE_TIMEOUT`
- `RECOVERY_BMC_CHUNK_SIZE`, `RECOVERY_BMC_LOG_LEVEL`
- `RECOVERY_BMC_FIRMWARE`
- `RECOVERY_BMC_CALIPTRA_FMC_RT`, `RECOVERY_BMC_SOC_MANIFEST`, `RECOVERY_BMC_MCU_RUNTIME`
- `RECOVERY_BMC_APP_CORE_IMAGES` (comma-separated paths)
- `RECOVERY_BMC_DOTENV` (optional explicit dotenv path)

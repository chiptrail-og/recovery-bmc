from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from ..errors import RecoveryError
from ..protocol import RecoveryCommand


def _import_i3cblaster():
    try:
        return importlib.import_module("i3cblaster")
    except ModuleNotFoundError as first_error:
        repo_root = Path(__file__).resolve().parents[3]
        default_submodule_py = repo_root / "I3CBlaster" / "python"
        env_override = os.environ.get("RECOVERY_BMC_I3CBLASTER_PYTHON", "").strip()
        candidate_paths = [Path(env_override).expanduser()] if env_override else []
        candidate_paths.append(default_submodule_py)

        for candidate in candidate_paths:
            if not candidate.exists():
                continue
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            try:
                return importlib.import_module("i3cblaster")
            except ModuleNotFoundError:
                continue

        raise RecoveryError(
            "i3cblaster module not found. Install via uv/source dependency or ensure "
            "I3CBlaster submodule is initialized (I3CBlaster/python), or set "
            "RECOVERY_BMC_I3CBLASTER_PYTHON."
        ) from first_error


class I3cTransport:
    def __init__(self, i3c, addr: int) -> None:
        self._i3c = i3c
        self._addr = addr

    @classmethod
    def open(
        cls,
        uart: str | None,
        clk_khz: int,
        addr: int | None,
        entdaa_addr: int,
    ) -> I3cTransport:
        i3c_mod = _import_i3cblaster()

        blaster = i3c_mod.i3cblaster(port=uart) if uart else i3c_mod.i3cblaster()
        if not blaster.i3c_rstdaa():
            raise RecoveryError("i3c_rstdaa failed")
        if not blaster.i3c_clk(clk_khz):
            raise RecoveryError(f"i3c_clk failed: {clk_khz} kHz")

        target_addr = addr
        if target_addr is None:
            if not blaster.i3c_entdaa(entdaa_addr):
                raise RecoveryError("i3c_entdaa failed")
            target_addr = entdaa_addr
        return cls(blaster, target_addr)

    def close(self) -> None:
        try:
            self._i3c.close()
        except Exception:
            pass

    def read(self, command: RecoveryCommand, length: int) -> bytes:
        data = self._i3c.i3c_sdr_writeread(self._addr, [int(command)], length)
        return bytes(data)

    def write(self, command: RecoveryCommand, data: bytes) -> None:
        self._i3c.i3c_sdr_write(self._addr, [int(command)] + list(data))

from __future__ import annotations

import importlib

from ..errors import RecoveryError
from ..protocol import RecoveryCommand


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
        try:
            i3c_mod = importlib.import_module("i3cblaster")
        except ModuleNotFoundError as error:
            raise RecoveryError(
                "i3cblaster module not found. Install it or add I3CBlaster/python to PYTHONPATH."
            ) from error

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

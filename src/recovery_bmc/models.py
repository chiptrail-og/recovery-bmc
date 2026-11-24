from __future__ import annotations

from dataclasses import dataclass

from .errors import RecoveryError


@dataclass(frozen=True)
class RecoveryImages:
    caliptra_fmc_rt: bytes
    soc_manifest: bytes
    mcu_runtime: bytes
    app_core_images: tuple[bytes, ...] = ()

    def get(self, index: int) -> bytes:
        if index == 0:
            return self.caliptra_fmc_rt
        if index == 1:
            return self.soc_manifest
        if index == 2:
            return self.mcu_runtime
        app_index = index - 3
        if 0 <= app_index < len(self.app_core_images):
            return self.app_core_images[app_index]
        raise RecoveryError(f"device requested unsupported recovery image index {index}")

    @staticmethod
    def name(index: int) -> str:
        names = ("Caliptra FMC/runtime", "SoC manifest", "MCU runtime")
        if 0 <= index < len(names):
            return names[index]
        if index >= 3:
            return f"App core image #{index - 2}"
        return "unknown image"


@dataclass(frozen=True)
class FifoStatus:
    full: bool
    write_index: int
    read_index: int
    size_dwords: int
    max_transfer_dwords: int

    def available_dwords(self) -> int:
        if self.full or self.size_dwords == 0:
            return 0
        if self.write_index >= self.read_index:
            used = self.write_index - self.read_index
        else:
            used = self.size_dwords - (self.read_index - self.write_index)
        return max(self.size_dwords - used, 0)

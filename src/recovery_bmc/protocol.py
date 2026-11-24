from __future__ import annotations

import enum
from typing import Protocol

PROT_CAP_MAGIC = b"OCP RECV"
USB_CONTROL_MAX_BYTES = 64


class RecoveryCommand(enum.IntEnum):
    PROT_CAP = 0x22
    DEVICE_STATUS = 0x24
    RECOVERY_CTRL = 0x26
    RECOVERY_STATUS = 0x27
    INDIRECT_FIFO_CTRL = 0x2D
    INDIRECT_FIFO_STATUS = 0x2E
    INDIRECT_FIFO_DATA = 0x2F


class DeviceStatus(enum.IntEnum):
    STATUS_PENDING = 0x0
    DEVICE_HEALTHY = 0x1
    DEVICE_ERROR = 0x2
    RECOVERY_MODE = 0x3
    RECOVERY_PENDING = 0x4
    RUNNING_RECOVERY_IMAGE = 0x5
    BOOT_FAILURE = 0xE
    FATAL_ERROR = 0xF


class DeviceRecoveryStatus(enum.IntEnum):
    NOT_IN_RECOVERY = 0x0
    AWAITING_IMAGE = 0x1
    BOOTING_IMAGE = 0x2
    SUCCESS = 0x3
    FAILED = 0xC
    AUTHENTICATION_ERROR = 0xD
    ERROR_ENTERING_RECOVERY = 0xE
    INVALID_CMS = 0xF


class RecoveryTransport(Protocol):
    def read(self, command: RecoveryCommand, length: int) -> bytes:
        """Read one OCP command response."""

    def write(self, command: RecoveryCommand, data: bytes) -> None:
        """Write one OCP command payload."""

    def close(self) -> None:
        """Release transport resources."""

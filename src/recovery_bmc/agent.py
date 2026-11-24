from __future__ import annotations

import struct
import sys
import time

from .errors import RecoveryError
from .models import FifoStatus, RecoveryImages
from .protocol import (
    PROT_CAP_MAGIC,
    USB_CONTROL_MAX_BYTES,
    DeviceRecoveryStatus,
    DeviceStatus,
    RecoveryCommand,
    RecoveryTransport,
)


class RecoveryAgent:
    def __init__(
        self,
        transport: RecoveryTransport,
        poll_interval: float = 0.01,
        state_timeout: float = 30.0,
    ) -> None:
        self.transport = transport
        self.cms = 0
        self.poll_interval = poll_interval
        self.state_timeout = state_timeout

    def run(self, images: RecoveryImages) -> None:
        self._check_capabilities()
        startup_deadline = time.monotonic() + self.state_timeout
        while True:
            status = self._device_status()
            if status == DeviceStatus.RECOVERY_MODE:
                break
            if status == DeviceStatus.RUNNING_RECOVERY_IMAGE:
                return
            if status not in (DeviceStatus.STATUS_PENDING, DeviceStatus.DEVICE_HEALTHY):
                raise RecoveryError(f"device is not ready for recovery: {status.name}")
            self._check_deadline(
                startup_deadline, "timed out waiting for the device to enter recovery mode"
            )
            time.sleep(self.poll_interval)

        self.transport.write(RecoveryCommand.RECOVERY_CTRL, bytes((0, 0, 0)))

        sent = [False, False, False]
        progress_deadline = time.monotonic() + self.state_timeout
        while True:
            self._check_deadline(
                progress_deadline, "timed out waiting for recovery state progress"
            )
            device_status = self._device_status()
            if device_status in (
                DeviceStatus.DEVICE_HEALTHY,
                DeviceStatus.RUNNING_RECOVERY_IMAGE,
            ):
                return
            if device_status not in (
                DeviceStatus.RECOVERY_MODE,
                DeviceStatus.RECOVERY_PENDING,
            ):
                raise RecoveryError(
                    f"recovery failed with device status {device_status.name}"
                )

            recovery_status, image_index = self._recovery_status()
            if recovery_status == DeviceRecoveryStatus.AWAITING_IMAGE:
                image = images.get(image_index)
                if sent[image_index]:
                    time.sleep(self.poll_interval)
                    continue
                self._send_fifo_image(image)
                sent[image_index] = True
                self._wait_for_recovery_pending()
                self.transport.write(
                    RecoveryCommand.RECOVERY_CTRL, bytes((self.cms, 0, 0x0F))
                )
                if all(sent):
                    return
                progress_deadline = time.monotonic() + self.state_timeout
            elif recovery_status in (
                DeviceRecoveryStatus.BOOTING_IMAGE,
                DeviceRecoveryStatus.SUCCESS,
            ):
                time.sleep(self.poll_interval)
            else:
                raise RecoveryError(
                    f"device reported recovery failure {recovery_status.name}"
                )

    def probe(self) -> None:
        response = self._read_exact(RecoveryCommand.PROT_CAP, 15)
        if response[:8] != PROT_CAP_MAGIC:
            raise RecoveryError("invalid PROT_CAP magic")
        version = f"{response[8]}.{response[9]}"
        capabilities = int.from_bytes(response[10:12], "little")
        device_status = self._device_status()
        recovery_status, image_index = self._recovery_status()
        print(
            f"[recovery-bmc] PROT_CAP magic={response[:8].decode('ascii')} "
            f"version={version} capabilities={capabilities:#06x}",
            file=sys.stderr,
        )
        print(f"[recovery-bmc] DEVICE_STATUS={device_status.name}", file=sys.stderr)
        print(
            f"[recovery-bmc] RECOVERY_STATUS={recovery_status.name} image_index={image_index}",
            file=sys.stderr,
        )

    def _check_capabilities(self) -> None:
        response = self._read_exact(RecoveryCommand.PROT_CAP, 15)
        if response[:8] != PROT_CAP_MAGIC:
            raise RecoveryError("invalid PROT_CAP magic")
        capabilities = int.from_bytes(response[10:12], "little")
        if capabilities & (1 << 4) == 0:
            raise RecoveryError("DEVICE_STATUS is not supported")
        if capabilities & (1 << 12) == 0:
            raise RecoveryError("FIFO CMS is not supported")

    def _device_status(self) -> DeviceStatus:
        response = self._read_exact(RecoveryCommand.DEVICE_STATUS, 7)
        try:
            return DeviceStatus(response[0])
        except ValueError as error:
            raise RecoveryError(f"invalid device status {response[0]:#04x}") from error

    def _recovery_status(self) -> tuple[DeviceRecoveryStatus, int]:
        response = self._read_exact(RecoveryCommand.RECOVERY_STATUS, 2)
        raw_status = response[0] & 0x0F
        try:
            status = DeviceRecoveryStatus(raw_status)
        except ValueError as error:
            raise RecoveryError(f"invalid recovery status {raw_status:#04x}") from error
        return status, response[0] >> 4

    def _wait_for_recovery_pending(self) -> None:
        deadline = time.monotonic() + self.state_timeout
        while self._device_status() != DeviceStatus.RECOVERY_PENDING:
            self._check_deadline(
                deadline, "timed out waiting for device to process recovery image"
            )
            time.sleep(self.poll_interval)

    def _send_fifo_image(self, image: bytes) -> None:
        padded_image = image + bytes((-len(image)) % 4)
        image_size_dwords = len(padded_image) // 4
        fifo_control = bytes((self.cms, 0)) + struct.pack("<I", image_size_dwords)
        self.transport.write(RecoveryCommand.INDIRECT_FIFO_CTRL, fifo_control)

        offset = 0
        deadline = time.monotonic() + self.state_timeout
        while offset < len(padded_image):
            status = self._fifo_status()
            available_dwords = status.available_dwords()
            if available_dwords == 0:
                self._check_deadline(deadline, "timed out waiting for FIFO space")
                time.sleep(self.poll_interval)
                continue
            max_bytes = min(status.max_transfer_dwords * 4, USB_CONTROL_MAX_BYTES)
            chunk_length = min(
                available_dwords * 4, max_bytes, len(padded_image) - offset
            )
            if chunk_length <= 0:
                raise RecoveryError("device reported invalid FIFO transfer size")
            self.transport.write(
                RecoveryCommand.INDIRECT_FIFO_DATA,
                padded_image[offset : offset + chunk_length],
            )
            offset += chunk_length

    def _fifo_status(self) -> FifoStatus:
        response = self._read_exact(RecoveryCommand.INDIRECT_FIFO_STATUS, 20)
        return FifoStatus(
            full=bool(response[0] & 2),
            write_index=int.from_bytes(response[4:8], "little"),
            read_index=int.from_bytes(response[8:12], "little"),
            size_dwords=int.from_bytes(response[12:16], "little"),
            max_transfer_dwords=int.from_bytes(response[16:20], "little"),
        )

    def _read_exact(self, command: RecoveryCommand, length: int) -> bytes:
        response = self.transport.read(command, length)
        if len(response) != length:
            raise RecoveryError(
                f"invalid {command.name} response length {len(response)}; expected {length}"
            )
        return response

    @staticmethod
    def _check_deadline(deadline: float, message: str) -> None:
        if time.monotonic() >= deadline:
            raise RecoveryError(message)

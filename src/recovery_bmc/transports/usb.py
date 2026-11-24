from __future__ import annotations

import time

import usb.core
import usb.util

from ..errors import RecoveryError
from ..protocol import RecoveryCommand

USB_INTERFACE = 0
USB_REQUEST_TYPE_IN = 0xA1
USB_REQUEST_TYPE_OUT = 0x21
USB_REQUEST = 0
USB_CONTROL_MAX_BYTES = 64


class PyUsbTransport:
    def __init__(self, device: usb.core.Device, timeout_ms: int) -> None:
        self._device = device
        self._timeout_ms = timeout_ms
        self._claimed = False

    @classmethod
    def open(
        cls,
        vendor_id: int,
        product_id: int,
        discovery_timeout: float,
        transfer_timeout: float,
    ) -> PyUsbTransport:
        deadline = time.monotonic() + discovery_timeout
        device = None
        while device is None:
            device = usb.core.find(idVendor=vendor_id, idProduct=product_id)
            if device is not None:
                break
            if time.monotonic() >= deadline:
                raise RecoveryError(
                    f"USB recovery device {vendor_id:04x}:{product_id:04x} was not found"
                )
            time.sleep(0.02)

        transport = cls(device, round(transfer_timeout * 1000))
        try:
            usb.util.claim_interface(device, USB_INTERFACE)
            transport._claimed = True
        except usb.core.USBError as error:
            usb.util.dispose_resources(device)
            raise RecoveryError("failed to claim OCP Recovery USB interface") from error
        return transport

    def close(self) -> None:
        if self._claimed:
            usb.util.release_interface(self._device, USB_INTERFACE)
            self._claimed = False
        usb.util.dispose_resources(self._device)

    def read(self, command: RecoveryCommand, length: int) -> bytes:
        try:
            response = self._device.ctrl_transfer(
                USB_REQUEST_TYPE_IN,
                USB_REQUEST,
                int(command),
                USB_INTERFACE,
                USB_CONTROL_MAX_BYTES,
                timeout=self._timeout_ms,
            )
        except usb.core.USBError as error:
            raise RecoveryError(f"OCP {command.name} read failed: {error}") from error
        return bytes(response[:length])

    def write(self, command: RecoveryCommand, data: bytes) -> None:
        try:
            written = self._device.ctrl_transfer(
                USB_REQUEST_TYPE_OUT,
                USB_REQUEST,
                int(command),
                USB_INTERFACE,
                data,
                timeout=self._timeout_ms,
            )
        except usb.core.USBError as error:
            raise RecoveryError(f"OCP {command.name} write failed: {error}") from error
        if written != len(data):
            raise RecoveryError(
                f"short OCP {command.name} write: {written} of {len(data)} bytes"
            )

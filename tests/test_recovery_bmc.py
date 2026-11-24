import pytest

from recovery_bmc import (
    DeviceRecoveryStatus,
    FifoStatus,
    RecoveryImages,
    RecoveryAgent,
    RecoveryCommand,
    RecoveryError,
    build_argument_parser,
    parse_i3c_addr,
    parse_usb_id,
)


class FakeTransport:
    def __init__(self, responses):
        self.responses = responses

    def read(self, command, length):
        return self.responses[(command, length)]

    def write(self, command, data):
        return None

    def close(self):
        return None


def test_parse_usb_id_accepts_hex():
    assert parse_usb_id("0x424") == 0x424


def test_parse_i3c_addr_range():
    assert parse_i3c_addr("0x7f") == 0x7F
    with pytest.raises(Exception):
        parse_i3c_addr("0x80")


def test_fifo_status_available_dwords_wrap():
    status = FifoStatus(
        full=False,
        write_index=2,
        read_index=6,
        size_dwords=8,
        max_transfer_dwords=16,
    )
    assert status.available_dwords() == 4


def test_recovery_status_decoding():
    transport = FakeTransport(
        {
            (RecoveryCommand.RECOVERY_STATUS, 2): bytes([0x21, 0x00]),
        }
    )
    agent = RecoveryAgent(transport)
    status, image_index = agent._recovery_status()
    assert status == DeviceRecoveryStatus.AWAITING_IMAGE
    assert image_index == 2


def test_read_exact_length_mismatch():
    transport = FakeTransport(
        {
            (RecoveryCommand.PROT_CAP, 15): b"\x00" * 14,
        }
    )
    agent = RecoveryAgent(transport)
    with pytest.raises(RecoveryError):
        agent._read_exact(RecoveryCommand.PROT_CAP, 15)


def test_recovery_images_support_app_core_indices():
    images = RecoveryImages(
        caliptra_fmc_rt=b"a",
        soc_manifest=b"b",
        mcu_runtime=b"c",
        app_core_images=(b"d", b"e"),
    )
    assert images.get(0) == b"a"
    assert images.get(2) == b"c"
    assert images.get(3) == b"d"
    assert images.get(4) == b"e"
    with pytest.raises(RecoveryError):
        images.get(5)


def test_cli_accepts_single_firmware_positional():
    parser = build_argument_parser()
    args = parser.parse_args(["firmware.bin", "--transport", "i3c"])
    assert str(args.firmware).endswith("firmware.bin")


def test_cli_accepts_chunk_size_and_no_activate():
    parser = build_argument_parser()
    args = parser.parse_args(["--chunk-size", "128", "--no-activate"])
    assert args.chunk_size == 128
    assert args.no_activate is True


def test_cli_accepts_multiple_app_images():
    parser = build_argument_parser()
    args = parser.parse_args(["--app-image", "app0.bin", "--app-image", "app1.bin"])
    assert [str(path) for path in args.app_image] == ["app0.bin", "app1.bin"]

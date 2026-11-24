from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PY_SCRIPT = REPO_ROOT / "scripts/netboot/start_dnsmasq.py"
SH_SCRIPT = REPO_ROOT / "scripts/netboot/start_dnsmasq.sh"


def _load_netboot_module():
    spec = importlib.util.spec_from_file_location("start_dnsmasq", PY_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_start_dnsmasq_python_requires_mandatory_settings(monkeypatch):
    module = _load_netboot_module()
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.delenv("RECOVERY_BMC_NETBOOT_INTERFACE", raising=False)
    monkeypatch.delenv("RECOVERY_BMC_NETBOOT_DHCP_RANGE", raising=False)
    monkeypatch.delenv("RECOVERY_BMC_TFTP_ROOT", raising=False)

    assert module.main([]) == 2


def test_start_dnsmasq_python_dry_run_writes_runtime_config(monkeypatch, tmp_path):
    module = _load_netboot_module()
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setenv("TMPDIR", str(tmp_path))

    tftp_root = tmp_path / "tftp-root"
    rc = module.main(
        [
            "--interface",
            "eth0",
            "--dhcp-range",
            "192.168.88.50,192.168.88.150,12h",
            "--tftp-root",
            str(tftp_root),
            "--bind-address",
            "192.168.88.1",
            "--dry-run",
        ]
    )

    assert rc == 0
    conf_path = tmp_path / "recovery-bmc-netboot" / "dnsmasq.conf"
    content = conf_path.read_text(encoding="utf-8")
    assert "interface=eth0" in content
    assert "dhcp-range=192.168.88.50,192.168.88.150,12h" in content
    assert f"tftp-root={tftp_root.resolve()}" in content
    assert "listen-address=192.168.88.1" in content


def test_start_dnsmasq_python_uses_env_defaults(monkeypatch, tmp_path):
    module = _load_netboot_module()
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("RECOVERY_BMC_NETBOOT_INTERFACE", "enx001122")
    monkeypatch.setenv("RECOVERY_BMC_NETBOOT_DHCP_RANGE", "10.0.0.50,10.0.0.99,4h")
    monkeypatch.setenv("RECOVERY_BMC_TFTP_ROOT", str(tmp_path / "env-root"))

    rc = module.main(["--dry-run"])

    assert rc == 0
    content = (tmp_path / "recovery-bmc-netboot" / "dnsmasq.conf").read_text(encoding="utf-8")
    assert "interface=enx001122" in content
    assert "dhcp-range=10.0.0.50,10.0.0.99,4h" in content


def test_start_dnsmasq_shell_help_works():
    result = subprocess.run(
        ["bash", str(SH_SCRIPT), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Environment defaults" in result.stdout

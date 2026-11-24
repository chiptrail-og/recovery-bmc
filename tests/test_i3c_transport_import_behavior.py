import types

import pytest

from recovery_bmc import RecoveryError
from recovery_bmc.transports import i3c as i3c_transport


def test_import_i3cblaster_prefers_normal_python_import(monkeypatch):
    sentinel = types.SimpleNamespace(name="i3cblaster")
    calls: list[str] = []

    def fake_import(name: str):
        calls.append(name)
        return sentinel

    monkeypatch.setattr(i3c_transport.importlib, "import_module", fake_import)

    result = i3c_transport._import_i3cblaster()

    assert result is sentinel
    assert calls == ["i3cblaster"]


def test_import_i3cblaster_falls_back_to_env_path(monkeypatch, tmp_path):
    fallback_path = tmp_path / "i3c-python"
    fallback_path.mkdir()
    monkeypatch.setenv("RECOVERY_BMC_I3CBLASTER_PYTHON", str(fallback_path))
    monkeypatch.setattr(i3c_transport.sys, "path", list(i3c_transport.sys.path))
    sentinel = types.SimpleNamespace(name="i3cblaster")
    attempts = {"count": 0}

    def fake_import(name: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ModuleNotFoundError("not found")
        return sentinel

    monkeypatch.setattr(i3c_transport.importlib, "import_module", fake_import)

    result = i3c_transport._import_i3cblaster()

    assert result is sentinel
    assert str(fallback_path) == i3c_transport.sys.path[0]


def test_import_i3cblaster_raises_recovery_error_when_missing(monkeypatch):
    monkeypatch.delenv("RECOVERY_BMC_I3CBLASTER_PYTHON", raising=False)
    monkeypatch.setattr(i3c_transport.sys, "path", list(i3c_transport.sys.path))

    def fake_import(_name: str):
        raise ModuleNotFoundError("missing")

    monkeypatch.setattr(i3c_transport.importlib, "import_module", fake_import)

    with pytest.raises(RecoveryError, match="i3cblaster module not found"):
        i3c_transport._import_i3cblaster()

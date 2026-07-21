"""Stub/helper wrapper behaviour tests."""

from tools.wrappers import bloodhound, responder, sliver


def test_responder_missing_binary(monkeypatch):
    monkeypatch.setattr("tools.wrappers.responder.shutil.which", lambda *_a, **_k: None)
    out = responder.scan("example.com")
    assert out["ready"] is False
    assert out["status"] == "missing_binary"


def test_responder_ready_without_interface(monkeypatch):
    monkeypatch.setattr(
        "tools.wrappers.responder.shutil.which",
        lambda name, **_k: "/usr/bin/responder" if name == "responder" else None,
    )

    class Completed:
        stdout = "usage: responder"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(
        "tools.wrappers.responder.subprocess.run",
        lambda *a, **k: Completed(),
    )
    out = responder.scan("example.com")
    assert out["ready"] is True
    assert out["status"] == "ready"


def test_bloodhound_needs_credentials(monkeypatch):
    monkeypatch.setattr(
        "tools.wrappers.bloodhound.shutil.which",
        lambda name, **_k: "/usr/local/bin/bloodhound-python"
        if name == "bloodhound-python"
        else None,
    )
    out = bloodhound.scan("dc.example.com")
    assert out["ready"] is True
    assert out["status"] == "needs_credentials"


def test_sliver_missing(monkeypatch):
    monkeypatch.setattr("tools.wrappers.sliver.shutil.which", lambda *_a, **_k: None)
    out = sliver.scan("10.0.0.5")
    assert out["ready"] is False
    assert out["status"] == "missing_binary"

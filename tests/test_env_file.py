import os
from pathlib import Path

from tools import env_file

KEYS = [
    "OXYLABS_PROXY_USERNAME",
    "OXYLABS_PROXY_PASSWORD",
    "OXYLABS_PROXY_HOST",
    "OXYLABS_PROXY_PORT",
    "OXYLABS_PROXY_PROTOCOL",
]


def test_upsert_replaces_existing_and_preserves_others(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text(
        "# header\n"
        "POSTGRES_PASSWORD=keep\n"
        "OXYLABS_PROXY_USERNAME=old\n"
        "OXYLABS_PROXY_PASSWORD=oldpass\n"
        "OXYLABS_PROXY_HOST=old.host\n"
        "# trailing comment\n",
        encoding="utf-8",
    )
    env_file.upsert_oxylabs_keys(
        str(path),
        {
            "OXYLABS_PROXY_USERNAME": "new",
            "OXYLABS_PROXY_PASSWORD": "newpass",
            "OXYLABS_PROXY_HOST": "pr.oxylabs.io",
            "OXYLABS_PROXY_PORT": "7777",
            "OXYLABS_PROXY_PROTOCOL": "http",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=keep" in text
    assert "# header" in text
    assert "# trailing comment" in text
    assert "OXYLABS_PROXY_USERNAME=new" in text
    assert "OXYLABS_PROXY_PASSWORD=newpass" in text
    assert "OXYLABS_PROXY_HOST=pr.oxylabs.io" in text
    assert "OXYLABS_PROXY_PORT=7777" in text
    assert "OXYLABS_PROXY_PROTOCOL=http" in text
    assert "oldpass" not in text


def test_upsert_appends_missing_keys(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text("FOO=1\n", encoding="utf-8")
    env_file.upsert_oxylabs_keys(
        str(path),
        {k: "v" for k in KEYS},
    )
    text = path.read_text(encoding="utf-8")
    assert text.startswith("FOO=1\n")
    for key in KEYS:
        assert f"{key}=v" in text


def test_clear_oxylabs_keys_blanks_values(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text(
        "OXYLABS_PROXY_USERNAME=u\nOXYLABS_PROXY_PASSWORD=p\nFOO=1\n",
        encoding="utf-8",
    )
    env_file.clear_oxylabs_keys(str(path))
    text = path.read_text(encoding="utf-8")
    assert "OXYLABS_PROXY_USERNAME=\n" in text
    assert "OXYLABS_PROXY_PASSWORD=\n" in text
    assert "FOO=1" in text

"""Tests for the WASM runtime loader."""

from __future__ import annotations

import pytest

from ootle._crypto import _wasm_runtime as rt
from ootle.errors import CryptoBridgeError


def _bogus_blob(_spec: rt.BlobSpec = rt.CORE_BLOB) -> bytes:
    return b"\x00asm\x00\x00\x00\x00bogus"


def _short_version(_spec: rt.BlobSpec = rt.CORE_BLOB) -> rt._Version:  # pyright: ignore[reportPrivateUsage]
    return rt._parse_version("only one line\n")  # pyright: ignore[reportPrivateUsage]


def test_load_blob_succeeds_and_returns_version() -> None:
    blob, version = rt.load_blob()
    assert blob.startswith(b"\x00asm")
    assert len(version.sha256) == 64


def test_load_with_stub_imports_instantiates() -> None:
    runtime = rt.WasmRuntime.load()
    assert runtime.memory is not None


def test_tampered_blob_raises_crypto_bridge_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rt, "_read_blob", _bogus_blob)
    with pytest.raises(CryptoBridgeError, match="SHA-256 mismatch"):
        rt.load_blob()


def test_tampered_version_raises_crypto_bridge_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rt, "_read_version", _short_version)
    with pytest.raises(CryptoBridgeError, match="VERSION"):
        rt.load_blob()


def test_parse_version_rejects_short_input() -> None:
    with pytest.raises(CryptoBridgeError):
        rt._parse_version("upstream: 0.0.0\n")  # pyright: ignore[reportPrivateUsage]

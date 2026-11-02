"""A test stand-in for the indexer's base64 CBOR (``Encoded<T>``) fields.

Python has no CBOR encoder for engine values (the decoding lives in the
vendored ``ootle-wasm-bor`` blob), so tests that build indexer responses by
hand wrap the JSON they expect the decoder to produce with :func:`encoded`.
:func:`install_fake_decoder` (autouse in ``conftest``) decodes those; any other
string, such as real CBOR from an upstream fixture or a live indexer, goes to
the real WASM decoder.
"""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any

from ootle._crypto import _bor

if TYPE_CHECKING:
    import pytest

_PREFIX = "fake-json:"  # ':' is not base64, so it never collides with a real encoding


def encoded(value: object) -> str:
    """Wrap *value* so the fake decoder returns it as the decoded JSON."""
    return _PREFIX + base64.b64encode(json.dumps(value).encode()).decode()


def install_fake_decoder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route :func:`encoded` values around WASM; pass everything else through."""
    real = _bor.decode

    def decode(kind: _bor.EncodedKind, value: str) -> Any:
        if value.startswith(_PREFIX):
            return json.loads(base64.b64decode(value.removeprefix(_PREFIX)))
        return real(kind, value)

    monkeypatch.setattr(_bor, "decode", decode)

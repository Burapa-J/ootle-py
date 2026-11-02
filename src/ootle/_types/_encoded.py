"""Decode the base64 CBOR (``Encoded<T>``) fields of indexer responses.

The decoding itself runs in the vendored ``ootle-wasm-bor`` blob (see
:mod:`ootle._crypto._bor`); this module adapts it to the JSON parsers: it
checks the field is a string and reports a bad encoding as ``ValueError``,
which the endpoint helpers wrap as :class:`~ootle.errors.IndexerClientError`.
"""

from __future__ import annotations

from typing import Any, cast

from ootle._crypto._bor import EncodedKind
from ootle.errors import CryptoBridgeError


def decode_encoded(kind: EncodedKind, value: object, field: str) -> Any:
    """Decode *value*, the base64 CBOR of a *kind*, into its JSON value.

    Raises:
        TypeError: *value* is not a string.
        ValueError: *value* is not a valid encoding of a *kind*.
    """
    from ootle._crypto import _bor  # noqa: PLC0415 - looked up per call so tests can swap it

    if not isinstance(value, str):
        msg = f"expected `{field}` to be a base64 string, got {type(value).__name__}"
        raise TypeError(msg)
    try:
        return _bor.decode(kind, value)
    except CryptoBridgeError as exc:
        msg = f"`{field}` is not a valid encoding: {exc}"
        raise ValueError(msg) from exc


def decode_encoded_object(kind: EncodedKind, value: object, field: str) -> dict[str, Any]:
    """:func:`decode_encoded`, requiring the decoded JSON to be an object."""
    decoded = decode_encoded(kind, value, field)
    if not isinstance(decoded, dict):
        msg = f"expected `{field}` to decode to an object, got {type(decoded).__name__}"
        raise TypeError(msg)
    return cast("dict[str, Any]", decoded)


__all__ = ["EncodedKind", "decode_encoded", "decode_encoded_object"]

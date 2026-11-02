"""Decoders for the CBOR values the indexer serves, via ``ootle-wasm-bor``.

Since tari-ootle 0.48 the indexer serves engine values (substate values,
execution results, receipts, events) as base64 of their CBOR encoding. The
vendored ``ootle-wasm-bor`` blob decodes one into the JSON the indexer used
to serve, so the existing JSON parsers keep working on the result.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from ._bridge import _abi, load_bor_bridge
from ._wasm_results import take_str_result


class EncodedKind(StrEnum):
    """The type a base64 CBOR value encodes, named by its decoder export."""

    SUBSTATE_VALUE = "decodeSubstateValue"
    EXECUTE_RESULT = "decodeExecuteResult"
    TRANSACTION_RECEIPT = "decodeTransactionReceipt"
    EVENT = "decodeEvent"


def decode(kind: EncodedKind, encoded: str) -> Any:
    """Decode base64 CBOR *encoded* as a *kind* and return its parsed JSON.

    Raises:
        CryptoBridgeError: *encoded* is not base64, or its bytes are not a
            complete encoding of a *kind*.
    """
    bridge = load_bor_bridge()
    with bridge.lock:
        ptr, length = _abi.alloc_str(bridge, encoded)
        ret = bridge.exports[str(kind)](bridge.store, ptr, length)
        text = take_str_result(bridge, ret, context=str(kind))
    return json.loads(text)


__all__ = ["EncodedKind", "decode"]

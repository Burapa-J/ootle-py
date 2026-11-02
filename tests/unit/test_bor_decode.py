"""``ootle-wasm-bor`` decoding of real indexer CBOR, end to end through the parsers.

The vectors in ``fixtures/bor_vectors.json`` are upstream's golden vectors,
so these run the vendored decoder blob, not the test stand-in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ootle._crypto._bor import EncodedKind, decode
from ootle._crypto._bridge import load_bor_bridge
from ootle._types._indexer_json import parse_indexer_substate, parse_transaction_result
from ootle._types.reject_reason import ExecutionFailure
from ootle._types.substate import ComponentSubstateValue, SubstateId, VaultSubstateValue
from ootle.errors import CryptoBridgeError

_VECTORS: dict[str, Any] = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "bor_vectors.json").read_text(encoding="utf-8")
)


def _get_response(encoded: str) -> dict[str, Any]:
    return {"version": 3, "state": {"up": {"substate": encoded}}, "verified": False}


def test_bor_bridge_is_a_singleton() -> None:
    assert load_bor_bridge() is load_bor_bridge()


def test_decodes_component_with_upgrade_rule() -> None:
    value = decode(EncodedKind.SUBSTATE_VALUE, _VECTORS["substate_component"])
    assert value["Component"]["header"]["upgrade_rule"] == "Locked"


def test_parses_component_substate() -> None:
    response = _get_response(_VECTORS["substate_component"])
    sub = parse_indexer_substate(SubstateId("component_c9"), response)
    assert sub is not None
    assert sub.version == 3
    assert isinstance(sub.value, ComponentSubstateValue)
    assert sub.value.template_address == "00" * 32


def test_parses_fungible_vault_substate() -> None:
    response = _get_response(_VECTORS["substate_fungible_vault"])
    sub = parse_indexer_substate(SubstateId("vault_v1"), response)
    assert sub is not None
    assert isinstance(sub.value, VaultSubstateValue)
    assert int(sub.value.balance) == 9577588913


def test_parses_fee_only_commit() -> None:
    payload = {"result": _VECTORS["finalized_accept_fee_reject_rest"]}
    is_finalized, outcome = parse_transaction_result(payload)
    assert is_finalized
    assert outcome is not None
    assert outcome.is_only_fee_commit
    assert outcome.reject_reason == ExecutionFailure(
        message="main intent failed", code="Unclassified"
    )


def test_parses_reject() -> None:
    _, outcome = parse_transaction_result({"result": _VECTORS["finalized_reject_access_denied"]})
    assert outcome is not None
    assert outcome.is_reject
    assert isinstance(outcome.reject_reason, ExecutionFailure)
    assert outcome.reject_reason.code == "AccessDenied"


def test_decodes_dry_run_result() -> None:
    result = decode(EncodedKind.EXECUTE_RESULT, _VECTORS["dry_run_result"])
    assert "Accept" in result["finalize"]["result"]


@pytest.mark.parametrize("bad", ["not base64!", "AAAA"])
def test_rejects_bad_encoding(bad: str) -> None:
    with pytest.raises(CryptoBridgeError):
        decode(EncodedKind.SUBSTATE_VALUE, bad)


def test_parser_reports_bad_encoding_as_value_error() -> None:
    with pytest.raises(ValueError, match="not a valid encoding"):
        parse_indexer_substate(SubstateId("component_c9"), _get_response("AAAA"))


def test_parser_rejects_non_string_encoding() -> None:
    with pytest.raises(TypeError, match="base64 string"):
        parse_indexer_substate(SubstateId("component_c9"), _get_response({"Component": {}}))  # pyright: ignore[reportArgumentType]

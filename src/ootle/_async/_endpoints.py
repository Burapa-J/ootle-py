"""Free-function endpoint helpers for :class:`AsyncIndexerTransport`.

Kept separate from ``_transport.py`` so both files stay under the
200-line cap. The transport class delegates the M4 endpoints (and the
lazily-started SSE transaction watcher) to these helpers; tests target
the transport methods (the helpers are an implementation detail).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from ootle._types._encoded import EncodedKind, decode_encoded_object
from ootle._types._indexer_json import (
    parse_submit_response,
    parse_transaction_result,
)
from ootle._types._json import parse_receipt
from ootle._types._json_helpers import require_str
from ootle._types.transaction import DryRunResult, TransactionId

if TYPE_CHECKING:
    from collections.abc import Callable

    import httpx

    from ootle._async._transport import AsyncIndexerTransport
    from ootle._async._watcher import AsyncTransactionWatcher
    from ootle._types.outcome import TransactionOutcome
    from ootle._types.receipt import TransactionReceipt


logger = logging.getLogger(__name__)


async def submit_transaction(transport: AsyncIndexerTransport, envelope_b64: str) -> TransactionId:
    """``POST /transactions`` → :class:`TransactionId`."""
    resp = await _post(transport, "transactions", {"transaction": envelope_b64})
    return parse_json_object(resp, parse_submit_response)


async def submit_transaction_dry_run(
    transport: AsyncIndexerTransport, envelope_b64: str
) -> DryRunResult:
    """``POST /transactions/dry-run`` → :class:`DryRunResult`."""
    resp = await _post(transport, "transactions/dry-run", {"transaction": envelope_b64})
    return parse_json_object(resp, _parse_dry_run)


def _parse_dry_run(body: dict[str, Any]) -> DryRunResult:
    tx_id = TransactionId(require_str(body, "transaction_id"))
    raw = decode_encoded_object(EncodedKind.EXECUTE_RESULT, body.get("result"), "result")
    return DryRunResult(transaction_id=tx_id, raw=raw)


async def get_transaction_result(
    transport: AsyncIndexerTransport, tx_id: TransactionId
) -> tuple[bool, TransactionOutcome | None]:
    """``GET /transactions/{id}/result`` → ``(is_finalized, outcome | None)``.

    Returns ``(False, None)`` for the ``Pending`` variant.
    """
    resp = await _get(transport, f"transactions/{tx_id}/result")
    return parse_json_object(resp, parse_transaction_result)


async def get_transaction_receipt(
    transport: AsyncIndexerTransport, tx_id: TransactionId
) -> TransactionReceipt | None:
    """``GET /transaction-receipts/{tx_id_hex}`` → :class:`TransactionReceipt` or ``None``.

    The Rust upstream derives the receipt address from the tx id; the
    bare tx id hex is the same key the indexer accepts.
    """
    resp = await transport._request(  # pyright: ignore[reportPrivateUsage]  # internal access
        "GET", f"transaction-receipts/{tx_id}", allow_404=True
    )
    if resp is None:
        return None
    return parse_json_object(resp, _parse_receipt_response)


def _parse_receipt_response(body: dict[str, Any]) -> TransactionReceipt:
    encoded = body.get("receipt")
    return parse_receipt(decode_encoded_object(EncodedKind.TRANSACTION_RECEIPT, encoded, "receipt"))


async def get_transaction_watcher(
    transport: AsyncIndexerTransport,
) -> AsyncTransactionWatcher | None:
    """Return *transport*'s SSE watcher, starting it on first call.

    Opens a single long-lived ``GET /events`` subscription so it is live
    before any transaction is submitted. A failure to subscribe is logged
    and yields ``None`` — the caller then watches finalisation by REST
    polling instead. The started watcher is cached on the transport.
    """
    existing = transport._tx_watcher  # pyright: ignore[reportPrivateUsage]  # internal access
    if existing is not None:
        return existing
    from ootle._async._watcher import AsyncTransactionWatcher  # noqa: PLC0415

    watcher = AsyncTransactionWatcher(transport.client, transport.url)
    try:
        await watcher.start()
    except Exception as exc:  # degrade to REST polling on any subscribe failure
        logger.warning("transaction watcher unavailable (/events): %s; using REST polling", exc)
        return None
    transport._tx_watcher = watcher  # pyright: ignore[reportPrivateUsage]  # internal access
    return watcher


async def _post(
    transport: AsyncIndexerTransport, path: str, payload: dict[str, Any]
) -> httpx.Response:
    resp = await transport._request("POST", path, json=payload)  # pyright: ignore[reportPrivateUsage]  # internal access
    assert resp is not None  # noqa: S101 — `allow_404=False`
    return resp


async def _get(transport: AsyncIndexerTransport, path: str) -> httpx.Response:
    resp = await transport._request("GET", path)  # pyright: ignore[reportPrivateUsage]  # internal access
    assert resp is not None  # noqa: S101 — `allow_404=False`
    return resp


def parse_json_object[T](resp: httpx.Response, parser: Callable[[dict[str, Any]], T]) -> T:
    """Decode *resp*'s JSON body as an object, run *parser*, wrap failures.

    Raises:
        IndexerClientError: The body is not JSON, not an object, or *parser*
            rejected its shape.
    """
    from ootle.errors import IndexerClientError  # noqa: PLC0415

    try:
        raw: object = resp.json()
        if not isinstance(raw, dict):
            msg = f"expected a JSON object, got {type(raw).__name__}"
            raise TypeError(msg)
        body = cast("dict[str, Any]", raw)
        return parser(body)
    except (ValueError, TypeError, KeyError) as exc:
        raise IndexerClientError(
            f"failed to parse indexer response: {exc}",
            status=resp.status_code,
            body=resp.text,
            url=str(resp.url),
        ) from exc

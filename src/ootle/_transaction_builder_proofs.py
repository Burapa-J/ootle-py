"""``ProofAuthorizationMixin`` — proof authorization windows on :class:`TransactionBuilder`.

Split out of ``_transaction_builder.py`` to keep that module under the
200-line limit. Since tari-ootle 0.49 a ``Proof`` authorizes only inside a
window the caller opens with ``AuthorizeProof`` and closes with
``DropProofAuthorization``; mirrors upstream ``TransactionBuilder::authorize_proof``,
``drop_proof_authorization`` and ``with_authorized_proof``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from ootle._types.instructions import AuthorizeProof, DropProofAuthorization

if TYPE_CHECKING:
    from collections.abc import Callable

    from ootle._types._tx_body import UnsignedTransactionV1Body
    from ootle._types.instructions import WorkspaceOffsetId


class ProofAuthorizationMixin:
    """Proof-window instructions shared into :class:`TransactionBuilder`."""

    __slots__ = ()

    _body: UnsignedTransactionV1Body

    if TYPE_CHECKING:

        def _resolve_workspace_offset(self, label: str) -> WorkspaceOffsetId: ...

    def authorize_proof(self, label: str) -> Self:
        """Open an authorization window over the workspace proof *label*.

        The proof authorizes the instructions that follow, until
        :meth:`drop_proof_authorization` closes the window.
        """
        proof = self._resolve_workspace_offset(label)
        self._body.instructions.append(AuthorizeProof(proof=proof))
        return self

    def drop_proof_authorization(self, label: str) -> Self:
        """Close the authorization window over the workspace proof *label*."""
        proof = self._resolve_workspace_offset(label)
        self._body.instructions.append(DropProofAuthorization(proof=proof))
        return self

    def with_authorized_proof(self, label: str, f: Callable[[Self], Self]) -> Self:
        """Add the instructions *f* builds inside a window over the workspace proof *label*.

        The proof is resolved once, before *f* runs, so the window closes over
        the same workspace item it opened even if *f* allocates new labels.
        """
        proof = self._resolve_workspace_offset(label)
        self._body.instructions.append(AuthorizeProof(proof=proof))
        f(self)
        self._body.instructions.append(DropProofAuthorization(proof=proof))
        return self

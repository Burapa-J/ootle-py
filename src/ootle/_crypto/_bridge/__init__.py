"""Bridge between Python and the vendored ``ootle-wasm`` blob.

Public surface (used by ``_wasm_provider``):

- :class:`Bridge` — handle bundling the runtime, exports, panic state, and
  the ABI helpers needed to call WASM exports.
- :func:`load_default_bridge` — process-wide cached factory for the core blob.
- :func:`load_bor_bridge` — the same for the ``ootle-wasm-bor`` decoder blob.
- :func:`define_imports` — passed to :func:`WasmRuntime.load` to wire
  ``__wbg_*`` host imports onto the linker.

This module is *internal*. No name exposed here is part of ``ootle``'s
public API.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import wasmtime

from ootle._crypto._wasm_runtime import BOR_BLOB, CORE_BLOB, BlobSpec, WasmRuntime

from ._imports import define_imports

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(slots=True)
class Bridge:
    """Mutable handle the host imports close over.

    Constructed empty, populated post-instantiation by :meth:`load_default`.
    The mutability is required because the host imports are defined
    *before* the WASM module is instantiated, but they need access to
    the resulting :class:`wasmtime.Memory` and exports map.
    """

    runtime: WasmRuntime | None = None
    panic_message: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def store(self) -> wasmtime.Store:
        return self._runtime.store

    @property
    def memory(self) -> wasmtime.Memory:
        return self._runtime.memory

    @property
    def exports(self) -> Mapping[str, Any]:
        return self._runtime.instance.exports(self._runtime.store)

    @property
    def _runtime(self) -> WasmRuntime:
        if self.runtime is None:
            msg = "Bridge used before runtime was attached"
            raise RuntimeError(msg)
        return self.runtime

    def consume_panic(self) -> str | None:
        msg = self.panic_message
        self.panic_message = None
        return msg

    @classmethod
    def load_default(cls, spec: BlobSpec = CORE_BLOB) -> Bridge:
        """Load a vendored blob (the core blob by default) and wire every host import."""
        bridge = cls()

        def _wire(store: wasmtime.Store, module: wasmtime.Module, linker: wasmtime.Linker) -> None:
            define_imports(store, module, linker, bridge)

        bridge.runtime = WasmRuntime.load(define_imports=_wire, spec=spec)
        # wasm-bindgen places initial setup behind an explicit start export.
        start = bridge.exports["__wbindgen_start"]
        if not isinstance(start, wasmtime.Func):
            msg = "WASM module is missing the __wbindgen_start export"
            raise RuntimeError(msg)
        start(bridge.store)
        return bridge


_singleton_lock = threading.Lock()
_singletons: dict[BlobSpec, Bridge] = {}


def load_default_bridge() -> Bridge:
    """Return the process-wide singleton bridge over the core blob."""
    return _load_singleton(CORE_BLOB)


def load_bor_bridge() -> Bridge:
    """Return the process-wide singleton bridge over the ``ootle-wasm-bor`` blob."""
    return _load_singleton(BOR_BLOB)


def _load_singleton(spec: BlobSpec) -> Bridge:
    """Return the process-wide bridge for *spec*, instantiating it once.

    Double-checked locking — ``functools.cache`` is not safe for the
    *first* call when multiple threads race; wasmtime drops the GIL
    inside ``Module``/``Instance`` construction, so two racers would
    each instantiate a separate engine and one would be silently
    discarded with native resources still attached.
    """
    existing = _singletons.get(spec)
    if existing is not None:
        return existing
    with _singleton_lock:
        bridge = _singletons.get(spec)
        if bridge is None:
            bridge = Bridge.load_default(spec)
            _singletons[spec] = bridge
        return bridge


__all__ = ["Bridge", "load_bor_bridge", "load_default_bridge"]

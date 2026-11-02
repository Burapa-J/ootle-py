"""Resource package for the vendored ``ootle_wasm_bor_bg.wasm`` blob.

``@tari-project/ootle-wasm-bor`` decodes the CBOR values the indexer serves
(substate values, execution results, receipts, events) into JSON. The blob
and its ``VERSION`` metadata load via ``importlib.resources.files``. Refresh
with ``make update-wasm WASM_VERSION=x.y.z``.
"""

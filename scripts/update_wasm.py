#!/usr/bin/env python3
"""Refresh a vendored ``@tari-project/ootle-wasm`` (or ``ootle-wasm-bor``) blob.

``--blob core`` (the default) vendors ``ootle-wasm``, which builds and signs
transactions; ``--blob bor`` vendors ``ootle-wasm-bor``, which decodes the
CBOR values the indexer serves. ``make update-wasm`` refreshes both.

Two sourcing modes are supported:

* **Registry** (the published flow)::

      make update-wasm WASM_VERSION=0.30.0
      uv run python scripts/update_wasm.py --version 0.30.0

  Downloads the npm tarball and extracts ``ootle_wasm_bg.wasm``.

* **Local build** (vendor a freshly built blob before the matching npm
  release ships)::

      uv run python scripts/update_wasm.py --from-pkg /path/to/pkg \
          --source "local build @ <commit> (crates/ootle_wasm)"

  Reads the blob straight from a ``wasm-pack`` output directory
  (``--from-pkg``) or an explicit file (``--from-file``), and stamps the
  ``VERSION`` ``upstream:`` label with a ``-local`` suffix so it is never
  mistaken for a registry release. See :mod:`_wasm_vendor` for the
  label/source rules.

Either way the script recomputes the blob's SHA-256 and rewrites the
vendored blob and ``VERSION`` file under ``--target-dir`` (the real
package directory by default). It deliberately does not auto-commit —
review the diff and open a PR.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import io
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

from _wasm_vendor import local_label, local_source, read_local_blob

_CRYPTO_DIR = Path(__file__).resolve().parent.parent / "src" / "ootle" / "_crypto"
# blob → (npm package name, blob file name, vendored directory)
BLOBS = {
    "core": ("ootle-wasm", "ootle_wasm_bg.wasm", _CRYPTO_DIR / "wasm"),
    "bor": ("ootle-wasm-bor", "ootle_wasm_bor_bg.wasm", _CRYPTO_DIR / "wasm_bor"),
}


def _registry_tarball_url(name: str, version: str) -> str:
    return f"https://registry.npmjs.org/@tari-project/{name}/-/{name}-{version}.tgz"


def _source_page_url(name: str, version: str) -> str:
    return f"https://www.npmjs.com/package/@tari-project/{name}/v/{version}"


def _download(url: str) -> bytes:
    print(f"  downloading {url}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 - https only
        return resp.read()


def _extract_blob(tgz_bytes: bytes, filename: str) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(tgz_bytes), mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.name.endswith(f"/{filename}"):
                fh = tar.extractfile(member)
                if fh is None:
                    msg = f"tar entry {member.name!r} is not a regular file"
                    raise RuntimeError(msg)
                return fh.read()
    msg = f"{filename!r} not found in tarball"
    raise RuntimeError(msg)


def _write_version(target: Path, version: str, sha256_hex: str, source: str) -> None:
    today = _dt.datetime.now(tz=_dt.UTC).date().isoformat()
    text = f"upstream: {version}\nsha256:   {sha256_hex}\nfetched:  {today}\nsource:   {source}\n"
    (target / "VERSION").write_text(text, encoding="utf-8")


def _print_summary(name: str, version: str, sha256_hex: str, blob_len: int, target: Path) -> None:
    line = (
        f"Vendored {name} {version} (sha256={sha256_hex[:12]}…, {blob_len:,} bytes) into {target}."
    )
    print(line)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--blob",
        choices=sorted(BLOBS),
        default="core",
        help="Which blob to vendor: core (ootle-wasm, default) or bor (ootle-wasm-bor).",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--version",
        default=os.environ.get("WASM_VERSION"),
        help="Upstream npm version to vendor from the registry (e.g. 0.30.0).",
    )
    source.add_argument(
        "--from-pkg",
        type=Path,
        metavar="DIR",
        help="Vendor the blob from a local wasm-pack output directory.",
    )
    source.add_argument(
        "--from-file",
        type=Path,
        metavar="PATH",
        help="Vendor the blob from an explicit local file.",
    )
    parser.add_argument(
        "--label",
        help="Override the VERSION upstream label (default for local modes: "
        "<package.json version>-local).",
    )
    parser.add_argument(
        "--source",
        help="Override the VERSION source line (default for local modes: 'local build (<path>)').",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        help="Directory to write the blob and VERSION into (default: the blob's package dir).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    name, filename, default_target = BLOBS[args.blob]

    if args.from_pkg is not None:
        blob = read_local_blob(args.from_pkg / filename)
        label = local_label(args.label, args.from_pkg)
        source = local_source(args.source, args.from_pkg)
    elif args.from_file is not None:
        blob = read_local_blob(args.from_file)
        label = local_label(args.label, None)
        source = local_source(args.source, args.from_file)
    elif args.version:
        blob = _extract_blob(_download(_registry_tarball_url(name, args.version)), filename)
        label, source = args.version, _source_page_url(name, args.version)
    else:
        parser.error("one of --version/--from-pkg/--from-file (or WASM_VERSION) is required")

    target: Path = args.target_dir or default_target
    target.mkdir(parents=True, exist_ok=True)
    sha256_hex = hashlib.sha256(blob).hexdigest()
    (target / filename).write_bytes(blob)
    _write_version(target, label, sha256_hex, source)

    _print_summary(name, label, sha256_hex, len(blob), target)
    print(
        "Next: review the diff, then run `make ci-verify-wasm` and `make ci`.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

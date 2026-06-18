# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2026 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Temporary web3-7 workaround for the ``valory/multisend`` contract.

web3 v7 returns call data as ``HexStr`` (``str``), but the pinned
``valory/multisend`` ``encode_data`` concatenates it as ``bytes`` without
coercion, so on-chain service minting (e.g. ``mech setup``) fails with
``TypeError: can't concat str to bytes``.

This script idempotently patches the *installed* multisend package to coerce
``str`` call data to ``bytes`` and re-aligns its fingerprint, so the package
still passes AEA's load-time consistency check. Run it after ``uv sync`` /
``autonomy packages sync`` and before ``mech setup``.

Remove this once the upstream open-autonomy fix lands and the ``valory/multisend``
package hash is bumped here.
"""

import sys
from pathlib import Path
from typing import Iterator, List

OLD_DATA_LINE = '    data = cast(bytes, tx.get("data", b""))'
NEW_DATA_BLOCK = (
    '    data = tx.get("data", b"")\n'
    "    if isinstance(data, str):\n"
    '        data = bytes.fromhex(data[2:] if data.startswith("0x") else data)\n'
    "    data = cast(bytes, data)"
)
OLD_FINGERPRINT = "bafybeihm6qv3bmsfxw2ex2itctgffbqrkqjva63rof6svjyctqknkfmahi"
NEW_FINGERPRINT = "bafybeiem5d46qb42ldd4rb5j5nyuw4g6cr3gp5edoczuhhtfi5kmdieivm"


def _multisend_dirs() -> Iterator[Path]:
    """Yield every importable ``valory/multisend`` package directory."""
    seen = set()
    roots = [Path(__file__).resolve().parents[1]]
    roots.extend(Path(entry) for entry in sys.path if entry)
    for root in roots:
        directory = root / "packages" / "valory" / "contracts" / "multisend"
        if directory in seen or not (directory / "contract.py").is_file():
            continue
        seen.add(directory)
        yield directory


def main() -> None:
    """Apply the coercion patch to every installed multisend package copy."""
    patched: List[str] = []
    for directory in _multisend_dirs():
        contract = directory / "contract.py"
        source = contract.read_text(encoding="utf-8")
        if "isinstance(data, str)" not in source:
            if OLD_DATA_LINE not in source:
                print(f"skip (unexpected content): {contract}")
                continue
            contract.write_text(
                source.replace(OLD_DATA_LINE, NEW_DATA_BLOCK), encoding="utf-8"
            )
        config = directory / "contract.yaml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                OLD_FINGERPRINT, NEW_FINGERPRINT
            ),
            encoding="utf-8",
        )
        patched.append(str(contract))

    if not patched:
        print("No multisend package found to patch.")
        return
    print("Patched multisend copies:")
    for path in patched:
        print(f"  {path}")


if __name__ == "__main__":
    main()

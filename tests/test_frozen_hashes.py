"""
Test SHA-256 hashes of frozen research artifacts.

Verifies that configs/baseline.yaml and reports/results/selected_pairs.csv
match their expected LF SHA-256 hashes.
See docs/FROZEN_DECISIONS.md Section 9 (Post-freeze addendum) for details
on the line-ending erratum and post-freeze modifications.
"""

import hashlib
from pathlib import Path

FROZEN_BASELINE_YAML_SHA256 = (
    "40f7c5f8b1ab2a0c53c5b7866c87d6a8bd3ad1bb1b30639f311a2f6426ec39d0"
)
FROZEN_SELECTED_PAIRS_CSV_SHA256 = (
    "6952604f8d142d24d8fdd7bd1db45804665e49f6917f73c1b393c9d47cf7124d"
)


def test_frozen_baseline_yaml_hash():
    path = Path("configs/baseline.yaml")
    assert path.exists(), f"{path} not found"
    content = path.read_bytes().replace(b"\r\n", b"\n")
    actual_hash = hashlib.sha256(content).hexdigest()
    assert (
        actual_hash == FROZEN_BASELINE_YAML_SHA256
    ), f"baseline.yaml hash mismatch: expected {FROZEN_BASELINE_YAML_SHA256}, got {actual_hash}"


def test_frozen_selected_pairs_csv_hash():
    path = Path("reports/results/selected_pairs.csv")
    assert path.exists(), f"{path} not found"
    content = path.read_bytes().replace(b"\r\n", b"\n")
    actual_hash = hashlib.sha256(content).hexdigest()
    assert (
        actual_hash == FROZEN_SELECTED_PAIRS_CSV_SHA256
    ), f"selected_pairs.csv hash mismatch: expected {FROZEN_SELECTED_PAIRS_CSV_SHA256}, got {actual_hash}"

from pathlib import Path

import pytest

from ai_lab_os.storage_exact_executor import ExactContractItem, build_exact_contract, execute_exact_contract, validate_exact_contract


def test_exact_contract_rejects_missing_approval_digest(tmp_path: Path) -> None:
    source = tmp_path / "a.pdf"
    source.write_bytes(b"pdf")
    item = ExactContractItem(str(source), str(tmp_path / "out" / "a.pdf"), "migrate", __import__("hashlib").sha256(b"pdf").hexdigest())
    contract = build_exact_contract((item,))
    ok, reason = validate_exact_contract(contract, None)
    assert ok is False
    assert "approval digest" in reason


def test_exact_contract_rejects_hash_change(tmp_path: Path) -> None:
    source = tmp_path / "a.pdf"
    source.write_bytes(b"old")
    item = ExactContractItem(str(source), str(tmp_path / "out" / "a.pdf"), "migrate", __import__("hashlib").sha256(b"old").hexdigest())
    contract = build_exact_contract((item,))
    source.write_bytes(b"changed")
    ok, reason = validate_exact_contract(contract, contract.digest)
    assert ok is False
    assert "hash changed" in reason


def test_exact_contract_rejects_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "a.pdf"
    destination = tmp_path / "out" / "a.pdf"
    source.write_bytes(b"pdf")
    destination.parent.mkdir()
    destination.write_bytes(b"existing")
    item = ExactContractItem(str(source), str(destination), "migrate", __import__("hashlib").sha256(b"pdf").hexdigest())
    contract = build_exact_contract((item,))
    ok, reason = validate_exact_contract(contract, contract.digest)
    assert ok is False
    assert "destination already exists" in reason


def test_exact_contract_executes_only_with_matching_digest(tmp_path: Path) -> None:
    source = tmp_path / "a.pdf"
    destination = tmp_path / "out" / "a.pdf"
    source.write_bytes(b"pdf")
    item = ExactContractItem(str(source), str(destination), "migrate", __import__("hashlib").sha256(b"pdf").hexdigest())
    contract = build_exact_contract((item,))
    with pytest.raises(ValueError):
        execute_exact_contract(contract, "wrong", quarantine_root=tmp_path / "q")
    results = execute_exact_contract(contract, contract.digest, quarantine_root=tmp_path / "q")
    assert len(results) == 1
    assert results[0].ok is True
    assert destination.read_bytes() == b"pdf"

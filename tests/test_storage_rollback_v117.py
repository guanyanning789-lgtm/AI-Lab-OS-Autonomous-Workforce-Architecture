from pathlib import Path

from ai_lab_os.storage_cleanup_plan import CleanupAction
from ai_lab_os.storage_rollback import StorageTransactionLedger, create_transaction, rollback_transaction


def test_transaction_ledger_roundtrip(tmp_path: Path) -> None:
    source = tmp_path / "old" / "file.bin"
    destination = tmp_path / "q" / "file.bin"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"data")
    tx = create_transaction(transaction_id="tx-1", action=CleanupAction.CLEAN, source=source, destination=destination)
    ledger = StorageTransactionLedger(tmp_path / "ledger.jsonl")
    ledger.append(tx)
    loaded = ledger.load("tx-1")
    assert loaded.sha256 == tx.sha256
    assert loaded.destination == str(destination)


def test_rollback_restores_original_path_and_verifies_hash(tmp_path: Path) -> None:
    source = tmp_path / "old" / "file.bin"
    destination = tmp_path / "q" / "file.bin"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"payload")
    tx = create_transaction(transaction_id="tx-2", action=CleanupAction.CLEAN, source=source, destination=destination)
    result = rollback_transaction(tx)
    assert result.ok is True
    assert source.read_bytes() == b"payload"
    assert not destination.exists()


def test_rollback_blocks_if_original_path_is_occupied(tmp_path: Path) -> None:
    source = tmp_path / "old" / "file.bin"
    destination = tmp_path / "q" / "file.bin"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"new-content")
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"old-content")
    tx = create_transaction(transaction_id="tx-3", action=CleanupAction.CLEAN, source=source, destination=destination)
    result = rollback_transaction(tx)
    assert result.ok is False
    assert source.read_bytes() == b"new-content"
    assert destination.exists()


def test_rollback_blocks_if_destination_changed(tmp_path: Path) -> None:
    source = tmp_path / "old" / "file.bin"
    destination = tmp_path / "q" / "file.bin"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"old-content")
    tx = create_transaction(transaction_id="tx-4", action=CleanupAction.CLEAN, source=source, destination=destination)
    destination.write_bytes(b"changed")
    result = rollback_transaction(tx)
    assert result.ok is False
    assert not source.exists()
    assert destination.read_bytes() == b"changed"

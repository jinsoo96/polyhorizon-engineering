from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

import polyhorizon.store as store_module
from polyhorizon.errors import ProtocolError
from polyhorizon.kernel import PureKernel, SessionState
from polyhorizon.models import Charter
from polyhorizon.store import FileSessionStore, MemorySessionStore, SessionStore

from .helpers import NOW, make_charter, make_proposal, receipt_for


@pytest.fixture(params=("memory", "file"))
def session_store(request: pytest.FixtureRequest, tmp_path: Path) -> SessionStore:
    if request.param == "memory":
        return MemorySessionStore()
    return FileSessionStore(tmp_path / "sessions")


def opened_state() -> tuple[PureKernel, Charter, SessionState]:
    kernel = PureKernel()
    charter = make_charter()
    result = kernel.open(charter, make_proposal(charter), now=NOW)
    assert result.effects
    return kernel, charter, result.state


def test_cas_requires_exactly_one_sequence_step_and_immutable_bindings(
    session_store: SessionStore,
) -> None:
    kernel, charter, current = opened_state()
    session_store.put_new(current)
    advanced = kernel.advance(
        charter,
        current,
        (receipt_for(current.requests[0], issued_at=NOW),),
        now=NOW,
    ).state

    with pytest.raises(ProtocolError, match="exactly once"):
        session_store.compare_and_swap(
            current.id,
            current.sequence,
            replace(advanced, sequence=current.sequence + 2),
        )
    with pytest.raises(ProtocolError, match="immutable"):
        session_store.compare_and_swap(
            current.id,
            current.sequence,
            replace(advanced, idempotency_key="different-key"),
        )


def test_store_resolves_session_by_idempotency_key(session_store: SessionStore) -> None:
    _, _, state = opened_state()
    assert session_store.get_by_idempotency(state.idempotency_key) is None
    session_store.put_new(state)
    assert session_store.get_by_idempotency(state.idempotency_key) == state
    assert isinstance(session_store, SessionStore)


def test_cas_cannot_drop_or_rewrite_persisted_protocol_entries(
    session_store: SessionStore,
) -> None:
    kernel, charter, current = opened_state()
    session_store.put_new(current)

    dropped_request = replace(
        current,
        sequence=current.sequence + 1,
        requests=current.requests[1:],
    )
    with pytest.raises(ProtocolError, match="preserve prior requests"):
        session_store.compare_and_swap(current.id, current.sequence, dropped_request)

    first = kernel.advance(
        charter,
        current,
        (receipt_for(current.requests[0], issued_at=NOW),),
        now=NOW,
    ).state
    session_store.compare_and_swap(current.id, current.sequence, first)
    completed = kernel.advance(
        charter,
        first,
        (receipt_for(first.pending_requests[0], issued_at=NOW),),
        now=NOW,
    ).state
    without_prior_receipt = replace(
        completed,
        receipts=tuple(item for item in completed.receipts if item.id != first.receipts[0].id),
    )
    with pytest.raises(ProtocolError, match="preserve prior receipts"):
        session_store.compare_and_swap(first.id, first.sequence, without_prior_receipt)


def test_cas_cannot_add_and_receipt_an_unpersisted_request(
    session_store: SessionStore,
) -> None:
    _, _, current = opened_state()
    session_store.put_new(current)
    invented_request = replace(
        current.requests[0],
        id="effect-invented",
        sequence=current.sequence + 1,
        group="invented-effect",
    )
    invented_receipt = receipt_for(invented_request, issued_at=NOW)
    invented = replace(
        current,
        sequence=current.sequence + 1,
        requests=(*current.requests, invented_request),
        receipts=(invented_receipt,),
    )

    with pytest.raises(ProtocolError, match="previously persisted requests"):
        session_store.compare_and_swap(current.id, current.sequence, invented)


def test_terminal_state_cannot_be_replaced(session_store: SessionStore) -> None:
    kernel, charter, current = opened_state()
    session_store.put_new(current)
    receipts = tuple(receipt_for(item, issued_at=NOW) for item in current.requests)
    decided = kernel.advance(charter, current, receipts, now=NOW).state
    session_store.compare_and_swap(current.id, current.sequence, decided)

    with pytest.raises(ProtocolError, match="terminal"):
        session_store.compare_and_swap(
            decided.id,
            decided.sequence,
            replace(decided, sequence=decided.sequence + 1),
        )


def test_file_put_new_is_atomic_per_idempotency_key(tmp_path: Path) -> None:
    _, _, state = opened_state()
    directory = tmp_path / "sessions"
    stores = (FileSessionStore(directory), FileSessionStore(directory))
    barrier = threading.Barrier(2)

    def create(store: FileSessionStore) -> SessionState:
        barrier.wait()
        return store.put_new(state)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(create, stores))

    assert {item.digest for item in results} == {state.digest}
    public_states = tuple(
        path for path in directory.glob("*.json") if not path.name.startswith(".")
    )
    assert len(public_states) == 1
    assert len(tuple(directory.glob(".idempotency-*.json"))) == 1


def test_persistent_lock_files_do_not_become_stale_ownership(tmp_path: Path) -> None:
    kernel, charter, current = opened_state()
    store = FileSessionStore(tmp_path / "sessions")
    store.put_new(current)
    first = kernel.advance(
        charter,
        current,
        (receipt_for(current.requests[0], issued_at=NOW),),
        now=NOW,
    ).state
    store.compare_and_swap(current.id, current.sequence, first)
    lock_files = tuple(store.directory.glob(".lock-session-*.lck"))
    assert len(lock_files) == 1

    completed = kernel.advance(
        charter,
        first,
        (receipt_for(first.pending_requests[0], issued_at=NOW),),
        now=NOW,
    ).state
    store.compare_and_swap(first.id, first.sequence, completed)
    assert store.get(first.id) == completed
    assert tuple(store.directory.glob(".lock-session-*.lck")) == lock_files


def test_file_store_rejects_path_shaped_ids_before_io(tmp_path: Path) -> None:
    directory = tmp_path / "sessions"
    store = FileSessionStore(directory)

    with pytest.raises(ValueError, match="not safe"):
        store.get("session/../../escape")
    assert not (tmp_path / "escape.json").exists()
    assert tuple(directory.iterdir()) == ()


def test_atomic_write_cleans_temporary_file_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, state = opened_state()
    store = FileSessionStore(tmp_path / "sessions")

    def fail_replace(source: object, destination: object) -> None:
        del source, destination
        raise OSError("simulated replace failure")

    monkeypatch.setattr(store_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        store.put_new(state)

    public_path = store.directory / f"{state.id}.json"
    assert not public_path.exists()
    assert not tuple(store.directory.glob("*.tmp"))
    assert not tuple(store.directory.glob(".*.tmp"))


def test_file_store_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    _, _, state = opened_state()
    store = FileSessionStore(tmp_path / "sessions")
    store.put_new(state)
    path = store.directory / f"{state.id}.json"
    value = path.read_text(encoding="utf-8")
    path.write_text(value.replace('"state": {', '"state": {}, "state": {', 1), encoding="utf-8")

    with pytest.raises(ProtocolError, match="unreadable"):
        store.get(state.id)

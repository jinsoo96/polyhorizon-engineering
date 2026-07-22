from __future__ import annotations

import errno
import hashlib
import importlib
import json
import os
import tempfile
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol, TypeVar, cast, runtime_checkable
from weakref import WeakValueDictionary

from polyhorizon.canonical import domain_digest, require_identifier, to_jsonable
from polyhorizon.errors import ConcurrentUpdateError, ManifestError, ProtocolError
from polyhorizon.kernel import SessionState, SessionStatus
from polyhorizon.models import EffectReceipt, EffectRequest
from polyhorizon.serde import session_from_dict

_Entry = TypeVar("_Entry", EffectRequest, EffectReceipt)
_PROCESS_LOCKS: WeakValueDictionary[str, threading.RLock] = WeakValueDictionary()
_PROCESS_LOCKS_GUARD = threading.Lock()
_WINDOWS_RESERVED_NAMES = {
    "aux",
    "clock$",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


class _WindowsFileLock(Protocol):
    LK_NBLCK: int
    LK_UNLCK: int

    def locking(self, descriptor: int, mode: int, byte_count: int) -> None: ...


@runtime_checkable
class SessionStore(Protocol):
    def get(self, session_id: str) -> SessionState | None: ...

    def get_by_idempotency(self, idempotency_key: str) -> SessionState | None: ...

    def put_new(self, state: SessionState) -> SessionState: ...

    def compare_and_swap(
        self, session_id: str, expected_sequence: int, state: SessionState
    ) -> None: ...


def _process_lock(path: Path) -> threading.RLock:
    key = os.path.normcase(os.fspath(path.resolve()))
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(key, threading.RLock())


def _lock_descriptor(descriptor: int) -> None:
    if os.name != "nt":
        fcntl = importlib.import_module("fcntl")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return

    msvcrt = cast(_WindowsFileLock, importlib.import_module("msvcrt"))

    while True:
        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            return
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise
            time.sleep(0.01)


def _unlock_descriptor(descriptor: int) -> None:
    if os.name != "nt":
        fcntl = importlib.import_module("fcntl")
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return

    msvcrt = cast(_WindowsFileLock, importlib.import_module("msvcrt"))
    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)


@contextmanager
def _exclusive_file_lock(path: Path) -> Iterator[None]:
    """Take an OS advisory lock; the file may persist, but ownership never does."""

    with _process_lock(path), path.open("a+b", buffering=0) as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
            os.fsync(stream.fileno())
        stream.seek(0)
        _lock_descriptor(stream.fileno())
        try:
            yield
        finally:
            stream.seek(0)
            _unlock_descriptor(stream.fileno())


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write_text(target: Path, payload: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        stream = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        descriptor = -1
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate stored JSON object key: {key}")
        result[key] = value
    return result


def _validate_expected_sequence(current: SessionState, expected_sequence: int) -> None:
    if current.sequence != expected_sequence:
        raise ConcurrentUpdateError(
            f"expected session sequence {expected_sequence}, found {current.sequence}"
        )


def _preserved_additions(
    previous: Sequence[_Entry], replacement: Sequence[_Entry], label: str
) -> tuple[_Entry, ...]:
    previous_by_id = {item.id: item for item in previous}
    replacement_by_id = {item.id: item for item in replacement}
    for identifier, item in previous_by_id.items():
        if replacement_by_id.get(identifier) != item:
            raise ProtocolError(f"replacement state must preserve prior {label}")

    # SessionState canonicalizes entries by id. Projecting the replacement back onto
    # prior ids is the canonical equivalent of preserving an append-only prefix.
    projected = tuple(item for item in replacement if item.id in previous_by_id)
    if projected != tuple(previous):
        raise ProtocolError(f"replacement state must preserve prior {label} order")
    return tuple(item for item in replacement if item.id not in previous_by_id)


def _validate_replacement(
    current: SessionState,
    replacement: SessionState,
    session_id: str,
    expected_sequence: int,
) -> None:
    _validate_expected_sequence(current, expected_sequence)
    if replacement.id != session_id or current.id != session_id:
        raise ProtocolError("replacement state does not belong to the stored session")
    if replacement.sequence != current.sequence + 1:
        raise ProtocolError("replacement state must advance the sequence exactly once")

    immutable_fields = (
        "idempotency_key",
        "charter_digest",
        "proposal_digest",
        "opened_at",
        "expires_at",
    )
    if any(getattr(replacement, field) != getattr(current, field) for field in immutable_fields):
        raise ProtocolError("replacement state changes an immutable session binding")
    if current.status is not SessionStatus.AWAITING_EFFECTS:
        raise ProtocolError("a terminal session cannot be replaced")
    if current.decision is not None:
        raise ProtocolError("a session decision is immutable")

    new_requests = _preserved_additions(current.requests, replacement.requests, "requests")
    new_receipts = _preserved_additions(current.receipts, replacement.receipts, "receipts")
    existing_request_digests = {item.digest for item in current.requests}
    if any(receipt.request_digest not in existing_request_digests for receipt in new_receipts):
        raise ProtocolError("new receipts may reference only previously persisted requests")

    if replacement.status is SessionStatus.ABORTED:
        if new_requests or new_receipts or replacement.decision is not None:
            raise ProtocolError("aborting a session may not mutate requests, receipts, or decision")
        return
    if replacement.status is SessionStatus.DECIDED:
        if new_requests or replacement.decision is None:
            raise ProtocolError("a decided replacement must preserve requests and add a decision")
        return
    if replacement.status is not SessionStatus.AWAITING_EFFECTS:
        raise ProtocolError("replacement state has an invalid status transition")
    if replacement.decision is not None:
        raise ProtocolError("an awaiting replacement cannot contain a decision")
    if not new_requests and not new_receipts:
        raise ProtocolError("an awaiting replacement must append a request or receipt")
    if any(request.sequence != replacement.sequence for request in new_requests):
        raise ProtocolError("new effect requests must be issued at the replacement sequence")


class MemorySessionStore:
    def __init__(self) -> None:
        self._states: dict[str, SessionState] = {}
        self._idempotency: dict[str, str] = {}
        self._lock = threading.RLock()

    def get(self, session_id: str) -> SessionState | None:
        require_identifier(session_id, "session_id")
        with self._lock:
            return self._states.get(session_id)

    def get_by_idempotency(self, idempotency_key: str) -> SessionState | None:
        require_identifier(idempotency_key, "session.idempotency_key")
        with self._lock:
            session_id = self._idempotency.get(idempotency_key)
            return None if session_id is None else self._states[session_id]

    def put_new(self, state: SessionState) -> SessionState:
        if state.sequence != 0:
            raise ProtocolError("a new session must start at sequence zero")
        with self._lock:
            existing_id = self._idempotency.get(state.idempotency_key)
            if existing_id is not None:
                existing = self._states[existing_id]
                if (
                    existing.charter_digest != state.charter_digest
                    or existing.proposal_digest != state.proposal_digest
                ):
                    raise ProtocolError("idempotency key is already bound to another proposal")
                return existing
            if state.id in self._states:
                raise ProtocolError("session id already exists")
            self._states[state.id] = state
            self._idempotency[state.idempotency_key] = state.id
            return state

    def compare_and_swap(
        self, session_id: str, expected_sequence: int, state: SessionState
    ) -> None:
        require_identifier(session_id, "session_id")
        with self._lock:
            current = self._states.get(session_id)
            if current is None:
                raise ProtocolError("session does not exist")
            _validate_replacement(current, state, session_id, expected_sequence)
            self._states[session_id] = state


class FileSessionStore:
    """Local restart-safe CAS store; remote deployments should implement SessionStore."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        if not self.directory.is_dir():
            raise ValueError("session store path is not a directory")

    @staticmethod
    def _safe_file_identifier(value: str, field: str) -> str:
        require_identifier(value, field)
        if "/" in value or ":" in value or value.endswith("."):
            raise ValueError(f"{field} is not safe for a local store path")
        if value.split(".", 1)[0].casefold() in _WINDOWS_RESERVED_NAMES:
            raise ValueError(f"{field} is not safe for a local store path")
        return value

    @staticmethod
    def _hashed_name(domain: str, value: str) -> str:
        material = f"polyhorizon-store\0{domain}\0{value}".encode()
        return hashlib.sha256(material).hexdigest()

    def _path(self, session_id: str) -> Path:
        safe_id = self._safe_file_identifier(session_id, "session_id")
        return self.directory / f"{safe_id}.json"

    def _session_lock_path(self, session_id: str) -> Path:
        safe_id = self._safe_file_identifier(session_id, "session_id")
        token = self._hashed_name("session", safe_id)
        return self.directory / f".lock-session-{token}.lck"

    def _idempotency_paths(self, idempotency_key: str) -> tuple[Path, Path]:
        require_identifier(idempotency_key, "session.idempotency_key")
        token = self._hashed_name("idempotency", idempotency_key)
        return (
            self.directory / f".idempotency-{token}.json",
            self.directory / f".lock-idempotency-{token}.lck",
        )

    def get(self, session_id: str) -> SessionState | None:
        path = self._path(session_id)
        lock_path = self._session_lock_path(session_id)
        with _exclusive_file_lock(lock_path):
            return self._read_session(path, session_id)

    def get_by_idempotency(self, idempotency_key: str) -> SessionState | None:
        index_path, lock_path = self._idempotency_paths(idempotency_key)
        with _exclusive_file_lock(lock_path):
            return self._lookup_idempotency(index_path, idempotency_key)

    def put_new(self, state: SessionState) -> SessionState:
        if state.sequence != 0:
            raise ProtocolError("a new session must start at sequence zero")
        path = self._path(state.id)
        session_lock_path = self._session_lock_path(state.id)
        index_path, idempotency_lock_path = self._idempotency_paths(state.idempotency_key)

        with _exclusive_file_lock(idempotency_lock_path):
            existing = self._lookup_idempotency(index_path, state.idempotency_key)
            if existing is not None:
                self._validate_idempotent_binding(existing, state, None)
                return existing
            with _exclusive_file_lock(session_lock_path):
                if path.exists():
                    raise ProtocolError("session id already exists")
                _atomic_write_text(path, self._encode(state))
            _atomic_write_text(index_path, self._encode_index(state))
            return state

    def compare_and_swap(
        self, session_id: str, expected_sequence: int, state: SessionState
    ) -> None:
        target = self._path(session_id)
        lock_path = self._session_lock_path(session_id)
        with _exclusive_file_lock(lock_path):
            current = self._read_session(target, session_id)
            if current is None:
                raise ProtocolError("session does not exist")
            _validate_replacement(current, state, session_id, expected_sequence)
            _atomic_write_text(target, self._encode(state))

    def _lookup_idempotency(self, index_path: Path, idempotency_key: str) -> SessionState | None:
        if index_path.exists():
            binding = self._read_index(index_path)
            if binding["idempotency_key"] != idempotency_key:
                raise ProtocolError("stored idempotency index does not match its key")
            existing_id = binding["session_id"]
            if not isinstance(existing_id, str):
                raise ProtocolError("stored idempotency index has an invalid session id")
            path = self._path(existing_id)
            existing = self._read_session(path, existing_id)
            if existing is None:
                raise ProtocolError("stored idempotency index references a missing session")
            if (
                binding["charter_digest"] != existing.charter_digest
                or binding["proposal_digest"] != existing.proposal_digest
                or existing.idempotency_key != idempotency_key
            ):
                raise ProtocolError("stored idempotency index conflicts with its session")
            return existing

        existing = self._find_idempotent(idempotency_key)
        if existing is not None:
            _atomic_write_text(index_path, self._encode_index(existing))
        return existing

    def _find_idempotent(self, idempotency_key: str) -> SessionState | None:
        found: SessionState | None = None
        for path in self.directory.glob("*.json"):
            if path.name.startswith("."):
                continue
            candidate = self._read_session(path, path.stem)
            if candidate is None or candidate.idempotency_key != idempotency_key:
                continue
            if found is not None and found.id != candidate.id:
                raise ProtocolError("multiple sessions share one idempotency key")
            found = candidate
        return found

    @staticmethod
    def _validate_idempotent_binding(
        existing: SessionState,
        proposed: SessionState,
        index: Mapping[str, object] | None,
    ) -> None:
        if (
            existing.charter_digest != proposed.charter_digest
            or existing.proposal_digest != proposed.proposal_digest
        ):
            raise ProtocolError("idempotency key is already bound to another proposal")
        if index is not None and (
            index["charter_digest"] != existing.charter_digest
            or index["proposal_digest"] != existing.proposal_digest
        ):
            raise ProtocolError("stored idempotency index conflicts with its session")

    @staticmethod
    def _read_session(path: Path, label: str) -> SessionState | None:
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
            state = FileSessionStore._decode(value, label)
        except (OSError, json.JSONDecodeError, ManifestError, ValueError, TypeError) as exc:
            if isinstance(exc, ProtocolError):
                raise
            raise ProtocolError(f"stored session is unreadable: {label}") from exc
        if state.id != label:
            raise ProtocolError("stored session id does not match its filename")
        return state

    @staticmethod
    def _encode(state: SessionState) -> str:
        envelope = {"state": to_jsonable(state), "state_digest": state.digest}
        return json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2) + "\n"

    @staticmethod
    def _decode(value: object, label: str) -> SessionState:
        if not isinstance(value, Mapping) or set(value) != {"state", "state_digest"}:
            raise ProtocolError(f"stored session envelope is invalid: {label}")
        expected = value.get("state_digest")
        if not isinstance(expected, str):
            raise ProtocolError(f"stored session digest is invalid: {label}")
        state = session_from_dict(value.get("state"))
        if state.digest != expected:
            raise ProtocolError(f"stored session digest does not match: {label}")
        return state

    @staticmethod
    def _encode_index(state: SessionState) -> str:
        binding = {
            "idempotency_key": state.idempotency_key,
            "session_id": state.id,
            "charter_digest": state.charter_digest,
            "proposal_digest": state.proposal_digest,
        }
        envelope = {
            "binding": binding,
            "binding_digest": domain_digest("session-idempotency-index", binding),
        }
        return json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2) + "\n"

    @staticmethod
    def _read_index(path: Path) -> Mapping[str, object]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ProtocolError("stored idempotency index is unreadable") from exc
        if not isinstance(value, Mapping) or set(value) != {"binding", "binding_digest"}:
            raise ProtocolError("stored idempotency index envelope is invalid")
        binding = value.get("binding")
        expected = value.get("binding_digest")
        required = {"idempotency_key", "session_id", "charter_digest", "proposal_digest"}
        if (
            not isinstance(binding, Mapping)
            or set(binding) != required
            or not isinstance(expected, str)
            or domain_digest("session-idempotency-index", binding) != expected
        ):
            raise ProtocolError("stored idempotency index digest does not match")
        return binding

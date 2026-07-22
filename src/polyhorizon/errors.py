class PolyhorizonError(Exception):
    """Base error for stable library-level failures."""


class ManifestError(PolyhorizonError):
    """The charter or proposal is structurally invalid."""


class ProtocolError(PolyhorizonError):
    """A state-machine or wire-protocol invariant was violated."""


class ConcurrentUpdateError(PolyhorizonError):
    """The caller attempted to replace a session from a stale sequence."""

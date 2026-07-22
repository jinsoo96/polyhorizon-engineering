from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from polyhorizon.canonical import (
    any_selector_matches,
    aware_datetime,
    domain_digest,
    freeze_mapping,
    parse_datetime,
    require_digest,
    require_identifier,
    unique_identifiers,
    unique_selectors,
)
from polyhorizon.errors import ManifestError

CHARTER_API = "polyhorizon.charter/v0.1"
PROPOSAL_API = "polyhorizon.proposal/v0.1"
EFFECT_API = "polyhorizon.effect/v0.1"

JsonObject = Mapping[str, Any]


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ManifestError(f"{path} must be an object with string keys")
    return value


def _sequence(value: object, path: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ManifestError(f"{path} must be an array")
    return value


def _string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise ManifestError(f"{path} must be a string")
    return value


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise ManifestError(f"{path} must be a boolean")
    return value


def _positive_integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ManifestError(f"{path} must be a positive integer")
    return value


def _only_keys(value: Mapping[str, object], allowed: set[str], path: str) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ManifestError(f"{path} contains unsupported fields: {', '.join(unexpected)}")


def _strings(value: object, path: str) -> tuple[str, ...]:
    return tuple(_string(item, f"{path}[]") for item in _sequence(value, path))


@dataclass(frozen=True, slots=True)
class SelectorSet:
    effects: tuple[str, ...]
    resources: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "effects", unique_selectors(self.effects, "selectors.effects"))
        object.__setattr__(
            self, "resources", unique_selectors(self.resources, "selectors.resources")
        )
        if not self.effects or not self.resources:
            raise ValueError("selectors require at least one effect and resource pattern")

    def matches(self, effect: str, resource: str) -> bool:
        return any_selector_matches(self.effects, effect) and any_selector_matches(
            self.resources, resource
        )

    @classmethod
    def from_dict(cls, value: object, path: str) -> SelectorSet:
        item = _mapping(value, path)
        _only_keys(item, {"effects", "resources"}, path)
        return cls(
            effects=_strings(item.get("effects"), f"{path}.effects"),
            resources=_strings(item.get("resources"), f"{path}.resources"),
        )

    def material(self) -> dict[str, object]:
        return {"effects": list(self.effects), "resources": list(self.resources)}


@dataclass(frozen=True, slots=True)
class Principal:
    id: str
    trust_domain: str
    adapter: str
    description: str = ""

    def __post_init__(self) -> None:
        require_identifier(self.id, "principal.id")
        require_identifier(self.trust_domain, "principal.trust_domain")
        require_identifier(self.adapter, "principal.adapter")
        if not isinstance(self.description, str):
            raise TypeError("principal.description must be a string")

    @classmethod
    def from_dict(cls, value: object, path: str) -> Principal:
        item = _mapping(value, path)
        _only_keys(item, {"id", "trust_domain", "adapter", "description"}, path)
        return cls(
            id=_string(item.get("id"), f"{path}.id"),
            trust_domain=_string(item.get("trust_domain"), f"{path}.trust_domain"),
            adapter=_string(item.get("adapter"), f"{path}.adapter"),
            description=_string(item.get("description", ""), f"{path}.description"),
        )

    def material(self) -> dict[str, str]:
        return {"id": self.id, "trust_domain": self.trust_domain, "adapter": self.adapter}


@dataclass(frozen=True, slots=True)
class Purpose:
    id: str
    owner: str
    specification_digest: str
    description: str = ""

    def __post_init__(self) -> None:
        require_identifier(self.id, "purpose.id")
        require_identifier(self.owner, "purpose.owner")
        require_digest(self.specification_digest, "purpose.specification_digest")
        if not isinstance(self.description, str):
            raise TypeError("purpose.description must be a string")

    @classmethod
    def from_dict(cls, value: object, path: str) -> Purpose:
        item = _mapping(value, path)
        _only_keys(item, {"id", "owner", "specification_digest", "description"}, path)
        return cls(
            id=_string(item.get("id"), f"{path}.id"),
            owner=_string(item.get("owner"), f"{path}.owner"),
            specification_digest=_string(
                item.get("specification_digest"), f"{path}.specification_digest"
            ),
            description=_string(item.get("description", ""), f"{path}.description"),
        )

    def material(self) -> dict[str, str]:
        return {
            "id": self.id,
            "owner": self.owner,
            "specification_digest": self.specification_digest,
        }


@dataclass(frozen=True, slots=True)
class Horizon:
    id: str
    kind: str
    owner: str
    selectors: SelectorSet
    observers: tuple[str, ...]
    minimum_trust_domains: int
    description: str = ""

    def __post_init__(self) -> None:
        require_identifier(self.id, "horizon.id")
        require_identifier(self.kind, "horizon.kind")
        require_identifier(self.owner, "horizon.owner")
        if not isinstance(self.selectors, SelectorSet):
            raise TypeError("horizon.selectors must be SelectorSet")
        object.__setattr__(
            self, "observers", unique_identifiers(self.observers, "horizon.observers")
        )
        if not self.observers:
            raise ValueError("horizon.observers must not be empty")
        if (
            isinstance(self.minimum_trust_domains, bool)
            or not isinstance(self.minimum_trust_domains, int)
            or self.minimum_trust_domains < 1
        ):
            raise ValueError("horizon.minimum_trust_domains must be a positive integer")
        if not isinstance(self.description, str):
            raise TypeError("horizon.description must be a string")

    @classmethod
    def from_dict(cls, value: object, path: str) -> Horizon:
        item = _mapping(value, path)
        _only_keys(
            item,
            {
                "id",
                "kind",
                "owner",
                "selectors",
                "observers",
                "minimum_trust_domains",
                "description",
            },
            path,
        )
        return cls(
            id=_string(item.get("id"), f"{path}.id"),
            kind=_string(item.get("kind"), f"{path}.kind"),
            owner=_string(item.get("owner"), f"{path}.owner"),
            selectors=SelectorSet.from_dict(item.get("selectors"), f"{path}.selectors"),
            observers=_strings(item.get("observers"), f"{path}.observers"),
            minimum_trust_domains=_positive_integer(
                item.get("minimum_trust_domains"), f"{path}.minimum_trust_domains"
            ),
            description=_string(item.get("description", ""), f"{path}.description"),
        )

    def material(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "owner": self.owner,
            "selectors": self.selectors.material(),
            "observers": list(self.observers),
            "minimum_trust_domains": self.minimum_trust_domains,
        }


@dataclass(frozen=True, slots=True)
class Standing:
    id: str
    representatives: tuple[str, ...]
    rights: tuple[str, ...]
    description: str = ""

    def __post_init__(self) -> None:
        require_identifier(self.id, "standing.id")
        object.__setattr__(
            self,
            "representatives",
            unique_identifiers(self.representatives, "standing.representatives"),
        )
        object.__setattr__(self, "rights", unique_identifiers(self.rights, "standing.rights"))
        if not self.representatives or not self.rights:
            raise ValueError("standing requires representatives and typed rights")
        if not isinstance(self.description, str):
            raise TypeError("standing.description must be a string")

    @classmethod
    def from_dict(cls, value: object, path: str) -> Standing:
        item = _mapping(value, path)
        _only_keys(item, {"id", "representatives", "rights", "description"}, path)
        return cls(
            id=_string(item.get("id"), f"{path}.id"),
            representatives=_strings(item.get("representatives"), f"{path}.representatives"),
            rights=_strings(item.get("rights"), f"{path}.rights"),
            description=_string(item.get("description", ""), f"{path}.description"),
        )

    def material(self) -> dict[str, object]:
        return {
            "id": self.id,
            "representatives": list(self.representatives),
            "rights": list(self.rights),
        }


class Reversibility(StrEnum):
    REVERSIBLE = "reversible"
    COMPENSATABLE = "compensatable"
    IRREVERSIBLE = "irreversible"


class ObligationMode(StrEnum):
    HARD = "hard"
    REVIEW = "review"
    ADVISORY = "advisory"


@dataclass(frozen=True, slots=True)
class Recourse:
    id: str
    standing_id: str
    owner: str
    executor: str
    mechanism: str
    applies_to: tuple[Reversibility, ...]
    deadline_seconds: int
    description: str = ""

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "recourse.id"),
            (self.standing_id, "recourse.standing_id"),
            (self.owner, "recourse.owner"),
            (self.executor, "recourse.executor"),
            (self.mechanism, "recourse.mechanism"),
        ):
            require_identifier(value, name)
        normalized = tuple(sorted(set(self.applies_to), key=lambda item: item.value))
        if len(normalized) != len(self.applies_to) or not normalized:
            raise ValueError("recourse.applies_to must be non-empty and unique")
        if not all(isinstance(item, Reversibility) for item in normalized):
            raise TypeError("recourse.applies_to values are invalid")
        object.__setattr__(self, "applies_to", normalized)
        if (
            isinstance(self.deadline_seconds, bool)
            or not isinstance(self.deadline_seconds, int)
            or self.deadline_seconds < 1
        ):
            raise ValueError("recourse.deadline_seconds must be a positive integer")
        if not isinstance(self.description, str):
            raise TypeError("recourse.description must be a string")

    @classmethod
    def from_dict(cls, value: object, path: str) -> Recourse:
        item = _mapping(value, path)
        _only_keys(
            item,
            {
                "id",
                "standing_id",
                "owner",
                "executor",
                "mechanism",
                "applies_to",
                "deadline_seconds",
                "description",
            },
            path,
        )
        try:
            applies_to = tuple(
                Reversibility(_string(value, f"{path}.applies_to[]"))
                for value in _sequence(item.get("applies_to"), f"{path}.applies_to")
            )
        except ValueError as exc:
            raise ManifestError(f"{path}.applies_to contains an invalid value") from exc
        return cls(
            id=_string(item.get("id"), f"{path}.id"),
            standing_id=_string(item.get("standing_id"), f"{path}.standing_id"),
            owner=_string(item.get("owner"), f"{path}.owner"),
            executor=_string(item.get("executor"), f"{path}.executor"),
            mechanism=_string(item.get("mechanism"), f"{path}.mechanism"),
            applies_to=applies_to,
            deadline_seconds=_positive_integer(
                item.get("deadline_seconds"), f"{path}.deadline_seconds"
            ),
            description=_string(item.get("description", ""), f"{path}.description"),
        )

    def material(self) -> dict[str, object]:
        return {
            "id": self.id,
            "standing_id": self.standing_id,
            "owner": self.owner,
            "executor": self.executor,
            "mechanism": self.mechanism,
            "applies_to": [item.value for item in self.applies_to],
            "deadline_seconds": self.deadline_seconds,
        }


@dataclass(frozen=True, slots=True)
class Obligation:
    id: str
    horizon_id: str
    bearer: str
    beneficiary: str
    predicate: str
    mode: ObligationMode
    selectors: SelectorSet
    recourse_ids: tuple[str, ...]
    observer_ids: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "obligation.id"),
            (self.horizon_id, "obligation.horizon_id"),
            (self.bearer, "obligation.bearer"),
            (self.beneficiary, "obligation.beneficiary"),
            (self.predicate, "obligation.predicate"),
        ):
            require_identifier(value, name)
        if not isinstance(self.mode, ObligationMode):
            raise TypeError("obligation.mode is invalid")
        if not isinstance(self.selectors, SelectorSet):
            raise TypeError("obligation.selectors must be SelectorSet")
        object.__setattr__(
            self, "recourse_ids", unique_identifiers(self.recourse_ids, "obligation.recourse_ids")
        )
        object.__setattr__(
            self, "observer_ids", unique_identifiers(self.observer_ids, "obligation.observer_ids")
        )
        if not isinstance(self.description, str):
            raise TypeError("obligation.description must be a string")

    @classmethod
    def from_dict(cls, value: object, path: str) -> Obligation:
        item = _mapping(value, path)
        _only_keys(
            item,
            {
                "id",
                "horizon_id",
                "bearer",
                "beneficiary",
                "predicate",
                "mode",
                "selectors",
                "recourse_ids",
                "observer_ids",
                "description",
            },
            path,
        )
        try:
            mode = ObligationMode(_string(item.get("mode"), f"{path}.mode"))
        except ValueError as exc:
            raise ManifestError(f"{path}.mode is invalid") from exc
        return cls(
            id=_string(item.get("id"), f"{path}.id"),
            horizon_id=_string(item.get("horizon_id"), f"{path}.horizon_id"),
            bearer=_string(item.get("bearer"), f"{path}.bearer"),
            beneficiary=_string(item.get("beneficiary"), f"{path}.beneficiary"),
            predicate=_string(item.get("predicate"), f"{path}.predicate"),
            mode=mode,
            selectors=SelectorSet.from_dict(item.get("selectors"), f"{path}.selectors"),
            recourse_ids=_strings(item.get("recourse_ids", []), f"{path}.recourse_ids"),
            observer_ids=_strings(item.get("observer_ids", []), f"{path}.observer_ids"),
            description=_string(item.get("description", ""), f"{path}.description"),
        )

    def material(self) -> dict[str, object]:
        return {
            "id": self.id,
            "horizon_id": self.horizon_id,
            "bearer": self.bearer,
            "beneficiary": self.beneficiary,
            "predicate": self.predicate,
            "mode": self.mode.value,
            "selectors": self.selectors.material(),
            "recourse_ids": list(self.recourse_ids),
            "observer_ids": list(self.observer_ids),
        }


@dataclass(frozen=True, slots=True)
class Mandate:
    id: str
    issuer: str
    principal: str
    actions: tuple[str, ...]
    resources: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    allow_amendment: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "mandate.id"),
            (self.issuer, "mandate.issuer"),
            (self.principal, "mandate.principal"),
        ):
            require_identifier(value, name)
        object.__setattr__(self, "actions", unique_selectors(self.actions, "mandate.actions"))
        object.__setattr__(self, "resources", unique_selectors(self.resources, "mandate.resources"))
        if not self.actions or not self.resources:
            raise ValueError("mandate requires action and resource selectors")
        object.__setattr__(self, "issued_at", aware_datetime(self.issued_at, "mandate.issued_at"))
        object.__setattr__(
            self, "expires_at", aware_datetime(self.expires_at, "mandate.expires_at")
        )
        if self.expires_at <= self.issued_at:
            raise ValueError("mandate expires_at must be later than issued_at")
        if not isinstance(self.allow_amendment, bool):
            raise TypeError("mandate.allow_amendment must be a boolean")

    @classmethod
    def from_dict(cls, value: object, path: str) -> Mandate:
        item = _mapping(value, path)
        _only_keys(
            item,
            {
                "id",
                "issuer",
                "principal",
                "actions",
                "resources",
                "issued_at",
                "expires_at",
                "allow_amendment",
            },
            path,
        )
        return cls(
            id=_string(item.get("id"), f"{path}.id"),
            issuer=_string(item.get("issuer"), f"{path}.issuer"),
            principal=_string(item.get("principal"), f"{path}.principal"),
            actions=_strings(item.get("actions"), f"{path}.actions"),
            resources=_strings(item.get("resources"), f"{path}.resources"),
            issued_at=parse_datetime(item.get("issued_at"), f"{path}.issued_at"),
            expires_at=parse_datetime(item.get("expires_at"), f"{path}.expires_at"),
            allow_amendment=_boolean(item.get("allow_amendment", False), f"{path}.allow_amendment"),
        )

    def material(self) -> dict[str, object]:
        return {
            "id": self.id,
            "issuer": self.issuer,
            "principal": self.principal,
            "actions": list(self.actions),
            "resources": list(self.resources),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "allow_amendment": self.allow_amendment,
        }


@dataclass(frozen=True, slots=True)
class AmendmentRule:
    approver_standings: tuple[str, ...]
    minimum_standings: int
    root_principal: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "approver_standings",
            unique_identifiers(self.approver_standings, "amendment.approver_standings"),
        )
        if not self.approver_standings:
            raise ValueError("amendment.approver_standings must not be empty")
        if (
            isinstance(self.minimum_standings, bool)
            or not isinstance(self.minimum_standings, int)
            or not 1 <= self.minimum_standings <= len(self.approver_standings)
        ):
            raise ValueError("amendment.minimum_standings is outside the approver set")
        require_identifier(self.root_principal, "amendment.root_principal")

    @classmethod
    def from_dict(cls, value: object, path: str) -> AmendmentRule:
        item = _mapping(value, path)
        _only_keys(item, {"approver_standings", "minimum_standings", "root_principal"}, path)
        return cls(
            approver_standings=_strings(
                item.get("approver_standings"), f"{path}.approver_standings"
            ),
            minimum_standings=_positive_integer(
                item.get("minimum_standings"), f"{path}.minimum_standings"
            ),
            root_principal=_string(item.get("root_principal"), f"{path}.root_principal"),
        )

    def material(self) -> dict[str, object]:
        return {
            "approver_standings": list(self.approver_standings),
            "minimum_standings": self.minimum_standings,
            "root_principal": self.root_principal,
        }


def _unique_by_id(values: Sequence[Any], path: str) -> tuple[Any, ...]:
    result = tuple(sorted(values, key=lambda item: item.id))
    ids = [item.id for item in result]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path} ids must be unique")
    return result


@dataclass(frozen=True, slots=True)
class Charter:
    id: str
    revision: str
    principals: tuple[Principal, ...]
    purposes: tuple[Purpose, ...]
    horizons: tuple[Horizon, ...]
    standings: tuple[Standing, ...]
    obligations: tuple[Obligation, ...]
    recourses: tuple[Recourse, ...]
    mandates: tuple[Mandate, ...]
    amendment: AmendmentRule
    api_version: str = CHARTER_API
    description: str = ""

    def __post_init__(self) -> None:
        require_identifier(self.id, "charter.id")
        require_identifier(self.revision, "charter.revision")
        if self.api_version != CHARTER_API:
            raise ValueError(f"charter.api_version must be {CHARTER_API}")
        for field_name in (
            "principals",
            "purposes",
            "horizons",
            "standings",
            "obligations",
            "recourses",
            "mandates",
        ):
            object.__setattr__(
                self, field_name, _unique_by_id(getattr(self, field_name), field_name)
            )
        if not self.principals or not self.purposes or not self.horizons:
            raise ValueError("charter requires principals, purposes, and horizons")
        if not isinstance(self.amendment, AmendmentRule):
            raise TypeError("charter.amendment must be AmendmentRule")
        if not isinstance(self.description, str):
            raise TypeError("charter.description must be a string")
        self._validate_references()

    def _validate_references(self) -> None:
        principals = self.principal_map
        horizons = self.horizon_map
        standings = self.standing_map
        recourses = self.recourse_map
        for purpose in self.purposes:
            self._require_reference(purpose.owner, principals, f"purpose {purpose.id} owner")
        for horizon in self.horizons:
            self._require_reference(horizon.owner, principals, f"horizon {horizon.id} owner")
            for observer in horizon.observers:
                self._require_reference(observer, principals, f"horizon {horizon.id} observer")
            domains = {principals[item].trust_domain for item in horizon.observers}
            if horizon.minimum_trust_domains > len(domains):
                raise ValueError(
                    f"horizon {horizon.id} requires more trust domains than its observers provide"
                )
        for standing in self.standings:
            for representative in standing.representatives:
                self._require_reference(
                    representative, principals, f"standing {standing.id} representative"
                )
        for recourse in self.recourses:
            self._require_reference(
                recourse.standing_id, standings, f"recourse {recourse.id} standing"
            )
            self._require_reference(recourse.owner, principals, f"recourse {recourse.id} owner")
            self._require_reference(
                recourse.executor, principals, f"recourse {recourse.id} executor"
            )
        for obligation in self.obligations:
            self._require_reference(
                obligation.horizon_id, horizons, f"obligation {obligation.id} horizon"
            )
            self._require_reference(
                obligation.bearer, principals, f"obligation {obligation.id} bearer"
            )
            self._require_reference(
                obligation.beneficiary, standings, f"obligation {obligation.id} beneficiary"
            )
            for recourse_id in obligation.recourse_ids:
                self._require_reference(
                    recourse_id, recourses, f"obligation {obligation.id} recourse"
                )
                if recourses[recourse_id].standing_id != obligation.beneficiary:
                    raise ValueError(
                        f"obligation {obligation.id} recourse beneficiary does not match"
                    )
            for observer in obligation.observer_ids:
                if observer not in horizons[obligation.horizon_id].observers:
                    raise ValueError(f"obligation {obligation.id} observer is outside its horizon")
        for mandate in self.mandates:
            self._require_reference(mandate.issuer, principals, f"mandate {mandate.id} issuer")
            self._require_reference(
                mandate.principal, principals, f"mandate {mandate.id} principal"
            )
        for approver_standing_id in self.amendment.approver_standings:
            self._require_reference(
                approver_standing_id,
                standings,
                "amendment approver standing",
            )
        self._require_reference(
            self.amendment.root_principal, principals, "amendment root principal"
        )

    @staticmethod
    def _require_reference(value: str, options: Mapping[str, object], field: str) -> None:
        if value not in options:
            raise ValueError(f"{field} references unknown id {value!r}")

    @property
    def principal_map(self) -> dict[str, Principal]:
        return {item.id: item for item in self.principals}

    @property
    def horizon_map(self) -> dict[str, Horizon]:
        return {item.id: item for item in self.horizons}

    @property
    def standing_map(self) -> dict[str, Standing]:
        return {item.id: item for item in self.standings}

    @property
    def obligation_map(self) -> dict[str, Obligation]:
        return {item.id: item for item in self.obligations}

    @property
    def recourse_map(self) -> dict[str, Recourse]:
        return {item.id: item for item in self.recourses}

    def material(self) -> dict[str, object]:
        return {
            "api_version": self.api_version,
            "id": self.id,
            "revision": self.revision,
            "principals": [item.material() for item in self.principals],
            "purposes": [item.material() for item in self.purposes],
            "horizons": [item.material() for item in self.horizons],
            "standings": [item.material() for item in self.standings],
            "obligations": [item.material() for item in self.obligations],
            "recourses": [item.material() for item in self.recourses],
            "mandates": [item.material() for item in self.mandates],
            "amendment": self.amendment.material(),
        }

    @property
    def digest(self) -> str:
        return domain_digest("charter", self.material())

    @classmethod
    def from_dict(cls, value: object, path: str = "$") -> Charter:
        item = _mapping(value, path)
        _only_keys(
            item,
            {
                "api_version",
                "id",
                "revision",
                "principals",
                "purposes",
                "horizons",
                "standings",
                "obligations",
                "recourses",
                "mandates",
                "amendment",
                "description",
            },
            path,
        )

        def many(name: str, factory: Any) -> tuple[Any, ...]:
            return tuple(
                factory(value, f"{path}.{name}[{index}]")
                for index, value in enumerate(_sequence(item.get(name), f"{path}.{name}"))
            )

        try:
            return cls(
                api_version=_string(item.get("api_version"), f"{path}.api_version"),
                id=_string(item.get("id"), f"{path}.id"),
                revision=_string(item.get("revision"), f"{path}.revision"),
                principals=many("principals", Principal.from_dict),
                purposes=many("purposes", Purpose.from_dict),
                horizons=many("horizons", Horizon.from_dict),
                standings=many("standings", Standing.from_dict),
                obligations=many("obligations", Obligation.from_dict),
                recourses=many("recourses", Recourse.from_dict),
                mandates=many("mandates", Mandate.from_dict),
                amendment=AmendmentRule.from_dict(item.get("amendment"), f"{path}.amendment"),
                description=_string(item.get("description", ""), f"{path}.description"),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ManifestError):
                raise
            raise ManifestError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class ImpactClaim:
    id: str
    effect: str
    resource: str
    horizons: tuple[str, ...]
    standings: tuple[str, ...]

    def __post_init__(self) -> None:
        require_identifier(self.id, "claim.id")
        require_identifier(self.effect, "claim.effect")
        require_identifier(self.resource, "claim.resource")
        object.__setattr__(self, "horizons", unique_identifiers(self.horizons, "claim.horizons"))
        object.__setattr__(self, "standings", unique_identifiers(self.standings, "claim.standings"))

    @classmethod
    def from_dict(cls, value: object, path: str) -> ImpactClaim:
        item = _mapping(value, path)
        _only_keys(item, {"id", "effect", "resource", "horizons", "standings"}, path)
        return cls(
            id=_string(item.get("id"), f"{path}.id"),
            effect=_string(item.get("effect"), f"{path}.effect"),
            resource=_string(item.get("resource"), f"{path}.resource"),
            horizons=_strings(item.get("horizons"), f"{path}.horizons"),
            standings=_strings(item.get("standings"), f"{path}.standings"),
        )

    def material(self) -> dict[str, object]:
        return {
            "id": self.id,
            "effect": self.effect,
            "resource": self.resource,
            "horizons": list(self.horizons),
            "standings": list(self.standings),
        }


@dataclass(frozen=True, slots=True)
class Proposal:
    id: str
    actor: str
    action: str
    claims: tuple[ImpactClaim, ...]
    reversibility: Reversibility
    artifact_digest: str
    base_charter_digest: str
    issued_at: datetime
    expires_at: datetime
    idempotency_key: str
    candidate_charter_digest: str | None = None
    ledger_root_digest: str | None = None
    api_version: str = PROPOSAL_API

    def __post_init__(self) -> None:
        if self.api_version != PROPOSAL_API:
            raise ValueError(f"proposal.api_version must be {PROPOSAL_API}")
        for value, name in (
            (self.id, "proposal.id"),
            (self.actor, "proposal.actor"),
            (self.action, "proposal.action"),
            (self.idempotency_key, "proposal.idempotency_key"),
        ):
            require_identifier(value, name)
        if not isinstance(self.reversibility, Reversibility):
            raise TypeError("proposal.reversibility is invalid")
        require_digest(self.artifact_digest, "proposal.artifact_digest")
        require_digest(self.base_charter_digest, "proposal.base_charter_digest")
        if self.candidate_charter_digest is not None:
            require_digest(self.candidate_charter_digest, "proposal.candidate_charter_digest")
        if self.ledger_root_digest is not None:
            require_digest(self.ledger_root_digest, "proposal.ledger_root_digest")
        if self.candidate_charter_digest is not None and self.ledger_root_digest is None:
            raise ValueError("amendment proposal requires a predecessor ledger root digest")
        claims = _unique_by_id(self.claims, "proposal.claims")
        if not claims:
            raise ValueError("proposal.claims must not be empty")
        object.__setattr__(self, "claims", claims)
        object.__setattr__(self, "issued_at", aware_datetime(self.issued_at, "proposal.issued_at"))
        object.__setattr__(
            self, "expires_at", aware_datetime(self.expires_at, "proposal.expires_at")
        )
        if self.expires_at <= self.issued_at:
            raise ValueError("proposal.expires_at must be later than issued_at")

    @property
    def is_amendment(self) -> bool:
        return self.candidate_charter_digest is not None

    def material(self) -> dict[str, object]:
        return {
            "api_version": self.api_version,
            "id": self.id,
            "actor": self.actor,
            "action": self.action,
            "claims": [item.material() for item in self.claims],
            "reversibility": self.reversibility.value,
            "artifact_digest": self.artifact_digest,
            "base_charter_digest": self.base_charter_digest,
            "candidate_charter_digest": self.candidate_charter_digest,
            "ledger_root_digest": self.ledger_root_digest,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "idempotency_key": self.idempotency_key,
        }

    @property
    def digest(self) -> str:
        return domain_digest("proposal", self.material())

    @classmethod
    def from_dict(cls, value: object, path: str = "$") -> Proposal:
        item = _mapping(value, path)
        _only_keys(
            item,
            {
                "api_version",
                "id",
                "actor",
                "action",
                "claims",
                "reversibility",
                "artifact_digest",
                "base_charter_digest",
                "candidate_charter_digest",
                "ledger_root_digest",
                "issued_at",
                "expires_at",
                "idempotency_key",
            },
            path,
        )
        candidate = item.get("candidate_charter_digest")
        ledger_root = item.get("ledger_root_digest")
        try:
            return cls(
                api_version=_string(item.get("api_version"), f"{path}.api_version"),
                id=_string(item.get("id"), f"{path}.id"),
                actor=_string(item.get("actor"), f"{path}.actor"),
                action=_string(item.get("action"), f"{path}.action"),
                claims=tuple(
                    ImpactClaim.from_dict(value, f"{path}.claims[{index}]")
                    for index, value in enumerate(_sequence(item.get("claims"), f"{path}.claims"))
                ),
                reversibility=Reversibility(
                    _string(item.get("reversibility"), f"{path}.reversibility")
                ),
                artifact_digest=_string(item.get("artifact_digest"), f"{path}.artifact_digest"),
                base_charter_digest=_string(
                    item.get("base_charter_digest"), f"{path}.base_charter_digest"
                ),
                candidate_charter_digest=(
                    None
                    if candidate is None
                    else _string(candidate, f"{path}.candidate_charter_digest")
                ),
                ledger_root_digest=(
                    None
                    if ledger_root is None
                    else _string(ledger_root, f"{path}.ledger_root_digest")
                ),
                issued_at=parse_datetime(item.get("issued_at"), f"{path}.issued_at"),
                expires_at=parse_datetime(item.get("expires_at"), f"{path}.expires_at"),
                idempotency_key=_string(item.get("idempotency_key"), f"{path}.idempotency_key"),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ManifestError):
                raise
            raise ManifestError(str(exc)) from exc


class ReceiptStatus(StrEnum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"
    UNCOVERED = "uncovered"


@dataclass(frozen=True, slots=True)
class EffectRequest:
    id: str
    kind: str
    session_id: str
    sequence: int
    charter_digest: str
    proposal_digest: str
    provider: str
    allowed_producers: tuple[str, ...]
    group: str
    payload: JsonObject
    expires_at: datetime
    api_version: str = EFFECT_API

    def __post_init__(self) -> None:
        if self.api_version != EFFECT_API:
            raise ValueError(f"effect request api_version must be {EFFECT_API}")
        for value, name in (
            (self.id, "effect.id"),
            (self.kind, "effect.kind"),
            (self.session_id, "effect.session_id"),
            (self.provider, "effect.provider"),
            (self.group, "effect.group"),
        ):
            require_identifier(value, name)
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValueError("effect.sequence must be a non-negative integer")
        require_digest(self.charter_digest, "effect.charter_digest")
        require_digest(self.proposal_digest, "effect.proposal_digest")
        object.__setattr__(
            self,
            "allowed_producers",
            unique_identifiers(self.allowed_producers, "effect.allowed_producers"),
        )
        if not self.allowed_producers:
            raise ValueError("effect.allowed_producers must not be empty")
        object.__setattr__(self, "payload", freeze_mapping(self.payload))
        object.__setattr__(self, "expires_at", aware_datetime(self.expires_at, "effect.expires_at"))

    def material(self) -> dict[str, object]:
        return {
            "api_version": self.api_version,
            "id": self.id,
            "kind": self.kind,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "charter_digest": self.charter_digest,
            "proposal_digest": self.proposal_digest,
            "provider": self.provider,
            "allowed_producers": list(self.allowed_producers),
            "group": self.group,
            "payload": self.payload,
            "expires_at": self.expires_at,
        }

    @property
    def digest(self) -> str:
        return domain_digest("effect-request", self.material())


@dataclass(frozen=True, slots=True)
class EffectReceipt:
    id: str
    request_digest: str
    producer: str
    status: ReceiptStatus
    evidence_digest: str
    result_digest: str
    issued_at: datetime
    details: JsonObject = field(default_factory=dict)
    api_version: str = EFFECT_API

    def __post_init__(self) -> None:
        if self.api_version != EFFECT_API:
            raise ValueError(f"effect receipt api_version must be {EFFECT_API}")
        require_identifier(self.id, "receipt.id")
        require_identifier(self.producer, "receipt.producer")
        require_digest(self.request_digest, "receipt.request_digest")
        require_digest(self.evidence_digest, "receipt.evidence_digest")
        require_digest(self.result_digest, "receipt.result_digest")
        if not isinstance(self.status, ReceiptStatus):
            raise TypeError("receipt.status is invalid")
        object.__setattr__(self, "issued_at", aware_datetime(self.issued_at, "receipt.issued_at"))
        object.__setattr__(self, "details", freeze_mapping(self.details))

    def material(self) -> dict[str, object]:
        return {
            "api_version": self.api_version,
            "id": self.id,
            "request_digest": self.request_digest,
            "producer": self.producer,
            "status": self.status.value,
            "evidence_digest": self.evidence_digest,
            "result_digest": self.result_digest,
            "issued_at": self.issued_at,
        }

    @property
    def digest(self) -> str:
        return domain_digest("effect-receipt", self.material())

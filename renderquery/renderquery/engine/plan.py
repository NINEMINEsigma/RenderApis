"""QueryPlan IR — JSON-serializable intermediate representation for queries.

This is the shared contract between all three frontends (Python SDK, CLI, HTTP).
A QueryPlan is a declarative description of:
  1. A data source (actions, resources, events)
  2. An ordered list of transformation steps (filter, sort, take, etc.)
  3. A final projection (field selection + artifact materialization)

The IR is intentionally simple — each step is a dict with an ``op`` string and
``params`` dict, so it can be trivially (de)serialized to/from JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SourceSpec:
    """Where the query rows originate from."""

    kind: str  # "actions" | "resources" | "events"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Step:
    """A single ordered transformation in the query pipeline."""

    op: str  # "filter" | "sort" | "take" | "take_percent" | "with_counter" | "group_by"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Projection:
    """A single column in the result set.

    For metadata fields, ``expr`` is a template like ``"{event_id}"`` or ``"{name}"``.
    For artifacts, ``expr`` is the artifact type name and ``artifact_params`` holds
    the generator parameters.
    """

    name: str
    expr: str
    is_artifact: bool = False
    artifact_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryPlan:
    """The complete query plan — source + steps + projection + output config."""

    source: SourceSpec
    steps: list[Step] = field(default_factory=list)
    projection: list[Projection] = field(default_factory=list)
    output_dir: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, d: dict) -> QueryPlan:
        source = SourceSpec(
            kind=d["source"]["kind"],
            params=d["source"].get("params", {}),
        )
        steps = [
            Step(op=s["op"], params=s.get("params", {}))
            for s in d.get("steps", [])
        ]
        projection = [
            Projection(
                name=p["name"],
                expr=p["expr"],
                is_artifact=p.get("is_artifact", False),
                artifact_params=p.get("artifact_params", {}),
            )
            for p in d.get("projection", [])
        ]
        return cls(
            source=source,
            steps=steps,
            projection=projection,
            output_dir=d.get("output_dir", ""),
        )

    @classmethod
    def from_json(cls, s: str) -> QueryPlan:
        return cls.from_dict(json.loads(s))
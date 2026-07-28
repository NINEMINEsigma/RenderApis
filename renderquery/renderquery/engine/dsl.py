"""Pipeline DSL — chainable query builder that compiles to QueryPlan IR.

Usage:
    plan = (Query()
        .from_actions(flags=int(ActionFlags.Drawcall))
        .with_gpu_counter(int(GPUCounter.EventGPUDuration))
        .sort_by("duration_gpu", desc=True)
        .take_percent(10)
        .project(
            event_id="{event_id}",
            name="{name}",
            duration_gpu="{duration_gpu}",
            screenshot=artifacts.screenshot(512, 512),
        )
        .to_file("./out/")
        .compile())

Each method returns a new Query (immutable), so chains can be reused and branched.
"""

from __future__ import annotations

import copy
from typing import Any

from .plan import QueryPlan, SourceSpec, Step, Projection
from .artifacts import ArtifactSpec


class Query:
    """Immutable chainable query builder."""

    def __init__(self, plan: QueryPlan | None = None):
        self._plan = plan or QueryPlan(source=SourceSpec(kind="actions"))

    # ------------------------------------------------------------------
    # Source
    # ------------------------------------------------------------------

    def from_actions(self, flags: int | None = None) -> Query:
        """Set the data source to action/event rows, optionally filtered by ActionFlags."""
        params = {"flags": flags} if flags is not None else {}
        q = self._clone()
        q._plan.source = SourceSpec(kind="actions", params=params)
        return q

    def from_resources(self) -> Query:
        """Set the data source to resource rows."""
        q = self._clone()
        q._plan.source = SourceSpec(kind="resources")
        return q

    def from_events(self) -> Query:
        """Set the data source to all event rows (no flag filtering)."""
        q = self._clone()
        q._plan.source = SourceSpec(kind="events")
        return q

    # ------------------------------------------------------------------
    # Transformations
    # ------------------------------------------------------------------

    def with_gpu_counter(self, counter: int) -> Query:
        """Enrich rows with GPU counter data (triggers FetchCounters on first use)."""
        q = self._clone()
        q._plan.steps.append(Step(op="with_counter", params={"counter": counter}))
        return q

    def filter(self, predicate: str) -> Query:
        """Filter rows by a predicate expression.

        The predicate is a string expression evaluated against each row's fields.
        Supports simple comparisons: ``"duration_gpu > 1000"``, ``"flags & 0x2"``,
        and Python eval-compatible expressions referencing row fields by name.
        """
        q = self._clone()
        q._plan.steps.append(Step(op="filter", params={"expr": predicate}))
        return q

    def sort_by(self, field: str, desc: bool = False) -> Query:
        """Sort rows by a field name."""
        q = self._clone()
        q._plan.steps.append(Step(op="sort", params={"field": field, "desc": desc}))
        return q

    def take(self, n: int) -> Query:
        """Take the first N rows."""
        q = self._clone()
        q._plan.steps.append(Step(op="take", params={"n": n}))
        return q

    def take_percent(self, pct: float) -> Query:
        """Take the top N% of rows (after any prior sorting)."""
        q = self._clone()
        q._plan.steps.append(Step(op="take_percent", params={"pct": pct}))
        return q

    def group_by(self, field: str) -> Query:
        """Group rows by a field. Following steps operate per-group."""
        q = self._clone()
        q._plan.steps.append(Step(op="group_by", params={"field": field}))
        return q

    # ------------------------------------------------------------------
    # Projection
    # ------------------------------------------------------------------

    def project(self, **kwargs: Any) -> Query:
        """Define the output columns.

        Metadata fields use template strings: ``event_id="{event_id}"``.
        Artifact fields pass an ArtifactSpec: ``screenshot=artifacts.screenshot(512, 512)``.
        """
        projections = []
        for name, value in kwargs.items():
            if isinstance(value, ArtifactSpec):
                projections.append(Projection(
                    name=name,
                    expr=value.kind,
                    is_artifact=True,
                    artifact_params=value.params,
                ))
            else:
                projections.append(Projection(
                    name=name,
                    expr=str(value),
                    is_artifact=False,
                ))
        q = self._clone()
        q._plan.projection = projections
        return q

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def to_file(self, output_dir: str) -> Query:
        """Set the output directory for materialized artifacts."""
        q = self._clone()
        q._plan.output_dir = output_dir
        return q

    # ------------------------------------------------------------------
    # Compile
    # ------------------------------------------------------------------

    def compile(self) -> QueryPlan:
        """Compile the chain into a QueryPlan IR."""
        return copy.deepcopy(self._plan)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _clone(self) -> Query:
        """Return a copy with a deep-copied plan so chains are immutable."""
        q = Query.__new__(Query)
        q._plan = copy.deepcopy(self._plan)
        return q
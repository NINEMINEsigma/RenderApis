"""Catalog — metadata loading and caching layer.

Wraps a renderdoc.ReplayController and presents its data as flat relational rows.
Three cache tiers:
  L0: Immediately available metadata (actions, chunks, resources) — loaded on init.
  L1: Lazy session cache (gpu_counters, resource_usage) — computed on first access.
  L2: Optional explicit persistence (save_index / load_index) — user-controlled.
"""

from __future__ import annotations

import json
import os
from typing import Any

import renderdoc as rd


def _flatten_actions(roots: list) -> list[dict]:
    """Recursively flatten the ActionDescription tree into event rows."""
    rows = []
    stack = [(a, None) for a in roots]
    while stack:
        action, parent_id = stack.pop()
        event_id = action.eventId
        row = {
            "event_id": event_id,
            "action_id": action.actionId,
            "parent_id": parent_id,
            "name": action.customName if action.customName else "",
            "flags": int(action.flags),
            "custom_name": action.customName,
            "num_indices": action.numIndices,
            "num_instances": action.numInstances,
            "base_vertex": action.baseVertex,
            "index_offset": action.indexOffset,
            "vertex_offset": action.vertexOffset,
            "instance_offset": action.instanceOffset,
            "draw_index": action.drawIndex,
            "dispatch_dimension": list(action.dispatchDimension),
            "dispatch_threads_dimension": list(action.dispatchThreadsDimension),
            "dispatch_base": list(action.dispatchBase),
            "copy_source": str(action.copySource) if action.copySource else "",
            "copy_destination": str(action.copyDestination) if action.copyDestination else "",
            "outputs": [str(o) for o in action.outputs],
            "depth_out": str(action.depthOut) if action.depthOut else "",
            "duration_cpu": 0.0,
            "duration_gpu": None,  # filled lazily by L1
        }
        # Collect CPU duration from the action's last event chunk
        # (will be enriched with chunk data in load_metadata)
        rows.append(row)
        # Push children in reverse so they pop in order
        for child in reversed(action.children):
            stack.append((child, event_id))
    return rows


def _action_name_from_chunk(action, sdfile) -> str:
    """Get a display name for an action from its chunk, falling back to customName."""
    if action.customName:
        return action.customName
    if action.events:
        chunk_idx = action.events[-1].chunkIndex
        if chunk_idx < len(sdfile.chunks):
            return sdfile.chunks[chunk_idx].name + "()"
    return ""


class Catalog:
    """Wraps ReplayController with relational views and caching."""

    def __init__(self, controller: rd.ReplayController):
        self._ctrl = controller
        self._events: list[dict] = []
        self._event_by_id: dict[int, dict] = {}
        self._chunks: list[dict] = []
        self._resources: list[dict] = []
        self._textures: list[dict] = []
        self._buffers: list[dict] = []
        self._gpu_counters: dict[int, dict[int, float]] = {}  # L1
        self._usage_cache: dict[str, list] = {}  # L1
        self._loaded = False

    # ------------------------------------------------------------------
    # L0: Immediate metadata
    # ------------------------------------------------------------------

    def load_metadata(self) -> None:
        """Load all L0 metadata. Call once after opening a capture."""
        # Actions → flat event rows
        roots = self._ctrl.GetRootActions()
        self._events = _flatten_actions(roots)

        # Enrich with chunk durations and display names
        sdfile = self._ctrl.GetStructuredFile()
        event_chunks = {}
        for action in roots:
            self._collect_event_chunks(action, sdfile, event_chunks)
        for row in self._events:
            eid = row["event_id"]
            if eid in event_chunks:
                info = event_chunks[eid]
                row["duration_cpu"] = info.get("duration_cpu", 0.0)
                if not row["name"]:
                    row["name"] = info.get("name", "")

        self._event_by_id = {r["event_id"]: r for r in self._events}

        # Chunks
        self._chunks = []
        for i, chunk in enumerate(sdfile.chunks):
            meta = chunk.metadata
            self._chunks.append({
                "index": i,
                "name": chunk.name,
                "chunk_id": meta.chunkID,
                "duration_micro": meta.durationMicro if meta.durationMicro >= 0 else None,
                "timestamp_micro": meta.timestampMicro,
                "thread_id": meta.threadID,
                "length": meta.length,
            })

        # Resources
        self._resources = []
        for res in self._ctrl.GetResources():
            self._resources.append({
                "resource_id": str(res.resourceId),
                "type": int(res.type),
                "type_name": str(res.type),
                "name": res.name,
                "autogenerated": res.autogeneratedName,
            })

        # Textures
        self._textures = []
        for tex in self._ctrl.GetTextures():
            self._textures.append({
                "resource_id": str(tex.resourceId),
                "format": str(tex.format.Name()),
                "dimension": tex.dimension,
                "type": int(tex.type),
                "width": tex.width,
                "height": tex.height,
                "depth": tex.depth,
                "cubemap": tex.cubemap,
                "mips": tex.mips,
                "arraysize": tex.arraysize,
                "byte_size": tex.byteSize,
            })

        # Buffers
        self._buffers = []
        for buf in self._ctrl.GetBuffers():
            self._buffers.append({
                "resource_id": str(buf.resourceId),
                "creation_flags": int(buf.creationFlags),
                "gpu_address": buf.gpuAddress,
                "length": buf.length,
            })

        self._loaded = True

    def _collect_event_chunks(self, action, sdfile, out: dict) -> None:
        """Recursively map eventId → {name, duration_cpu} from chunks."""
        for ev in action.events:
            idx = ev.chunkIndex
            if idx < len(sdfile.chunks):
                chunk = sdfile.chunks[idx]
                dur = chunk.metadata.durationMicro
                out[ev.eventId] = {
                    "name": chunk.name + "()",
                    "duration_cpu": float(dur) if dur >= 0 else 0.0,
                }
        for child in action.children:
            self._collect_event_chunks(child, sdfile, out)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def controller(self) -> rd.ReplayController:
        return self._ctrl

    @property
    def events(self) -> list[dict]:
        if not self._loaded:
            self.load_metadata()
        return self._events

    @property
    def chunks(self) -> list[dict]:
        if not self._loaded:
            self.load_metadata()
        return self._chunks

    @property
    def resources(self) -> list[dict]:
        if not self._loaded:
            self.load_metadata()
        return self._resources

    @property
    def textures(self) -> list[dict]:
        if not self._loaded:
            self.load_metadata()
        return self._textures

    @property
    def buffers(self) -> list[dict]:
        if not self._loaded:
            self.load_metadata()
        return self._buffers

    def get_event(self, event_id: int) -> dict | None:
        if not self._loaded:
            self.load_metadata()
        return self._event_by_id.get(event_id)

    def get_actions(self, flags: int | None = None) -> list[dict]:
        """Return event rows, optionally filtered by ActionFlags bitmask."""
        rows = self.events
        if flags is not None:
            rows = [r for r in rows if r["flags"] & flags]
        return rows

    # ------------------------------------------------------------------
    # L1: Lazy session cache
    # ------------------------------------------------------------------

    def fetch_gpu_counters(self, counter: int) -> dict[int, float]:
        """Fetch GPU counter results for all events, cached per session.

        Args:
            counter: GPUCounter enum value (e.g. int(GPUCounter.EventGPUDuration)).

        Returns:
            Dict mapping eventId → counter value (float, in microseconds for duration).
        """
        if counter in self._gpu_counters:
            return self._gpu_counters[counter]

        gpu_counter = rd.GPUCounter(counter)
        desc = self._ctrl.DescribeCounter(gpu_counter)
        results = self._ctrl.FetchCounters([gpu_counter])
        mapped = {}
        for r in results:
            if desc.resultByteWidth == 8:
                val = float(r.value.d)
            elif desc.resultByteWidth == 4:
                val = float(r.value.f)
            else:
                val = float(r.value.d)
            # EventGPUDuration returns seconds; convert to microseconds
            if counter == int(rd.GPUCounter.EventGPUDuration):
                val = val * 1e6
            mapped[r.eventId] = val

        self._gpu_counters[counter] = mapped
        # Backfill into event rows
        for eid, val in mapped.items():
            if eid in self._event_by_id:
                self._event_by_id[eid]["duration_gpu"] = val

        return mapped

    def get_usage(self, resource_id: str) -> list[dict]:
        """Get resource usage events, cached per session."""
        if resource_id in self._usage_cache:
            return self._usage_cache[resource_id]

        rid = rd.ResourceId()
        # ResourceId from string — SWIG returns ResourceId via int constructor
        # We use the string representation to reconstruct
        usages = self._ctrl.GetUsage(_str_to_resource_id(resource_id))
        result = [
            {"event_id": u.eventId, "usage": int(u.usage)}
            for u in usages
        ]
        self._usage_cache[resource_id] = result
        return result

    # ------------------------------------------------------------------
    # L2: Explicit persistence
    # ------------------------------------------------------------------

    def save_index(self, path: str) -> None:
        """Export the current L1 cache (gpu_counters, usage) to a JSON file."""
        data = {
            "gpu_counters": {
                str(k): {str(eid): v for eid, v in vals.items()}
                for k, vals in self._gpu_counters.items()
            },
            "usage_cache": dict(self._usage_cache),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_index(self, path: str) -> None:
        """Load a previously saved L2 index into L1 cache."""
        if not os.path.exists(path):
            return
        with open(path) as f:
            data = json.load(f)
        for k, vals in data.get("gpu_counters", {}).items():
            counter = int(k)
            self._gpu_counters[counter] = {int(eid): v for eid, v in vals.items()}
            # Backfill event rows
            for eid, val in self._gpu_counters[counter].items():
                if eid in self._event_by_id:
                    self._event_by_id[eid]["duration_gpu"] = val
        self._usage_cache = data.get("usage_cache", {})


def _str_to_resource_id(rid_str: str) -> rd.ResourceId:
    """Parse a ResourceId from its string representation.

    RenderDoc's SWIG binding exposes ResourceId with a numeric underlying value.
    The string form is typically the numeric ID, but may vary by API.
    """
    if not rid_str or rid_str == "ResourceId::Null()":
        return rd.ResourceId.Null()
    # Try parsing as integer (the common case for SWIG ResourceId)
    try:
        return rd.ResourceId(int(rid_str))
    except (ValueError, TypeError):
        return rd.ResourceId.Null()
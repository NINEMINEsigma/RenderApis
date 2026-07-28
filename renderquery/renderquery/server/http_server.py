"""HTTP Server frontend — FastAPI with no-queue, 409-on-busy semantics.

Endpoints:
    POST   /capture/load    Load a capture file          → 200 | 409
    POST   /capture/unload   Unload current capture       → 200
    POST   /query            Execute a query plan         → 200 | 409
    GET    /status           Server state                 → 200
    GET    /schema           Available fields & artifacts → 200
    POST   /index/save       Persist L1 cache             → 200
    POST   /index/load       Load L1 cache from file      → 200

No request queuing. If the executor is busy, POST /query returns 409 immediately.
Single capture model: loading a new capture unloads the previous one.
"""

from __future__ import annotations

import threading
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# ------------------------------------------------------------------ #
# Pydantic request/response models
# ------------------------------------------------------------------ #

class LoadRequest(BaseModel):
    path: str


class QueryRequest(BaseModel):
    plan: dict[str, Any]
    output_dir: str = "./out/"


class IndexRequest(BaseModel):
    path: str


# ------------------------------------------------------------------ #
# Singleton server state (one capture, one executor, protected by lock)
# ------------------------------------------------------------------ #

class ServerState:
    def __init__(self):
        self._lock = threading.Lock()
        self._client = None
        self._capture_path: str | None = None

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    @property
    def client(self):
        return self._client

    @property
    def capture_path(self) -> str | None:
        return self._capture_path

    @property
    def is_busy(self) -> bool:
        return self._client is not None and self._client.is_busy

    @property
    def is_loaded(self) -> bool:
        return self._client is not None

    def load_capture(self, path: str) -> None:
        from renderquery.sdk import RenderQueryClient

        # Unload existing capture first
        if self._client is not None:
            self._client.shutdown()
            self._client = None
            self._capture_path = None

        self._client = RenderQueryClient(path)
        self._capture_path = path

    def unload_capture(self) -> None:
        if self._client is not None:
            self._client.shutdown()
            self._client = None
            self._capture_path = None

    def execute_plan(self, plan_dict: dict, output_dir: str) -> list[dict]:
        from renderquery.engine.plan import QueryPlan
        from renderquery.engine.executor import ExecutorBusy

        if self._client is None:
            raise RuntimeError("No capture loaded")

        plan = QueryPlan.from_dict(plan_dict)
        try:
            return self._client._executor.execute(plan, output_dir)
        except ExecutorBusy:
            raise

    def save_index(self, path: str) -> None:
        if self._client is None:
            raise RuntimeError("No capture loaded")
        self._client.save_index(path)

    def load_index(self, path: str) -> None:
        if self._client is None:
            raise RuntimeError("No capture loaded")
        self._client.load_index(path)


_state = ServerState()


# ------------------------------------------------------------------ #
# FastAPI app
# ------------------------------------------------------------------ #

app = FastAPI(
    title="RenderQuery",
    description="Database-like query engine for RenderDoc replay snapshots",
    version="0.1.0",
)


@app.post("/capture/load")
def capture_load(req: LoadRequest):
    """Load a capture file. Unloads any previously loaded capture."""
    with _state.lock:
        try:
            _state.load_capture(req.path)
            return {"ok": True, "capture": req.path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/capture/unload")
def capture_unload():
    """Unload the current capture."""
    with _state.lock:
        _state.unload_capture()
        return {"ok": True}


@app.post("/query")
def query(req: QueryRequest):
    """Execute a query plan. Returns 409 if executor is busy."""
    with _state.lock:
        if _state.is_busy:
            raise HTTPException(status_code=409, detail="executor is busy")

        if not _state.is_loaded:
            raise HTTPException(status_code=400, detail="no capture loaded")

        try:
            results = _state.execute_plan(req.plan, req.output_dir)
            return {"results": results}
        except Exception as e:
            if "busy" in str(e).lower():
                raise HTTPException(status_code=409, detail="executor is busy")
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
def status():
    """Get current server state."""
    return {
        "loaded": _state.is_loaded,
        "busy": _state.is_busy,
        "capture_path": _state.capture_path,
    }


@app.get("/schema")
def schema():
    """List available fields, artifact types, and step operations."""
    return {
        "sources": ["actions", "events", "resources"],
        "fields": {
            "actions": [
                "event_id", "action_id", "parent_id", "name", "custom_name",
                "flags", "num_indices", "num_instances", "base_vertex",
                "index_offset", "vertex_offset", "instance_offset",
                "draw_index", "dispatch_dimension", "dispatch_threads_dimension",
                "dispatch_base", "copy_source", "copy_destination",
                "outputs", "depth_out", "duration_cpu", "duration_gpu",
            ],
            "resources": [
                "resource_id", "type", "type_name", "name", "autogenerated",
            ],
        },
        "artifact_types": [
            "screenshot", "mesh", "texture_data", "shader_disasm", "buffer_data",
        ],
        "step_ops": [
            "with_counter", "filter", "sort", "take", "take_percent", "group_by",
        ],
        "counters": {
            "EventGPUDuration": 1,
            "InputVerticesRead": 2,
            "IAPrimitives": 3,
            "GSPrimitives": 4,
            "RasterizerInvocations": 5,
            "RasterizedPrimitives": 6,
            "SamplesPassed": 7,
            "VSInvocations": 8,
            "HSInvocations": 9,
            "DSInvocations": 10,
            "GSInvocations": 11,
            "PSInvocations": 12,
            "CSInvocations": 13,
            "ASInvocations": 14,
            "MSInvocations": 15,
        },
    }


@app.post("/index/save")
def index_save(req: IndexRequest):
    """Persist L1 cache to a JSON file."""
    with _state.lock:
        try:
            _state.save_index(req.path)
            return {"ok": True, "saved": req.path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/index/load")
def index_load(req: IndexRequest):
    """Load L1 cache from a JSON file."""
    with _state.lock:
        try:
            _state.load_index(req.path)
            return {"ok": True, "loaded": req.path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------ #
# Entry point for `renderquery serve`
# ------------------------------------------------------------------ #

def run_server(host: str = "127.0.0.1", port: int = 8080, capture_path: str | None = None):
    """Start the HTTP server (blocking)."""
    import uvicorn

    if capture_path:
        with _state.lock:
            try:
                _state.load_capture(capture_path)
                print(f"Loaded capture: {capture_path}")
            except Exception as e:
                print(f"Warning: Failed to load capture on startup: {e}", flush=True)

    print(f"RenderQuery server listening on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
"""Python SDK — in-process client for RenderQuery.

Usage:
    from renderquery.sdk import RenderQueryClient
    from renderdoc import GPUCounter, ActionFlags, MeshDataStage
    from renderquery.engine import artifacts

    client = RenderQueryClient("capture.rdc")
    results = (client.query()
        .from_actions(flags=int(ActionFlags.Drawcall))
        .with_gpu_counter(int(GPUCounter.EventGPUDuration))
        .sort_by("duration_gpu", desc=True)
        .take_percent(10)
        .project(
            event_id="{event_id}",
            name="{name}",
            duration_gpu="{duration_gpu}",
            screenshot=artifacts.screenshot(512, 512),
            mesh=artifacts.mesh(stage="PostVS"),
        )
        .to_file("./out/")
        .execute())
    client.shutdown()
"""

from __future__ import annotations

import renderdoc as rd

from ..engine.executor import Executor, ExecutorBusy
from ..engine.dsl import Query


def open_capture(capture_path: str, replay_options: rd.ReplayOptions | None = None) -> rd.ReplayController:
    """Open a capture file and create a ReplayController.

    This follows the same pattern as rdtest/analyse.open_capture but is self-contained
    so the SDK doesn't depend on the test framework.
    """
    if replay_options is None:
        replay_options = rd.ReplayOptions()

    cap = rd.OpenCaptureFile()
    result = cap.OpenFile(capture_path, "", None)
    if result != rd.ResultCode.Succeeded:
        cap.Shutdown()
        raise RuntimeError(f"Couldn't open '{capture_path}': {result}")

    if not cap.LocalReplaySupport():
        cap.Shutdown()
        raise RuntimeError(f"Capture '{capture_path}' cannot be replayed locally")

    result, controller = cap.OpenCapture(replay_options, None)
    cap.Shutdown()

    if result != rd.ResultCode.Succeeded:
        raise RuntimeError(f"Couldn't initialise replay: {result}")

    return controller


class RenderQueryClient:
    """In-process client wrapping a single capture and executor."""

    def __init__(self, capture_path: str, replay_options: rd.ReplayOptions | None = None):
        self._capture_path = capture_path
        self._controller = open_capture(capture_path, replay_options)
        self._executor = Executor(self._controller)

    @property
    def executor(self) -> Executor:
        return self._executor

    @property
    def is_busy(self) -> bool:
        return self._executor.is_busy

    @property
    def capture_path(self) -> str:
        return self._capture_path

    def query(self) -> Query:
        """Return a new Query builder for chaining."""
        return Query()

    def execute(self, query: Query, output_dir: str = "./out") -> list[dict]:
        """Compile and execute a query, returning result rows."""
        plan = query.compile()
        return self._executor.execute(plan, output_dir)

    def save_index(self, path: str) -> None:
        """Persist L1 cache (gpu_counters, usage) to a JSON file."""
        self._executor.catalog.save_index(path)

    def load_index(self, path: str) -> None:
        """Load a previously saved index into L1 cache."""
        self._executor.catalog.load_index(path)

    def shutdown(self) -> None:
        """Close the replay controller and release resources."""
        if self._controller is not None:
            self._controller.Shutdown()
            self._controller = None
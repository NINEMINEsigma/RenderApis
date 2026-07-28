"""CLI frontend — stdin/stdout JSON interface for RenderQuery.

Commands:
    renderquery load <capture.rdc>          Load a capture file
    renderquery query [--plan JSON]         Execute a query plan (JSON from --plan or stdin)
    renderquery status                       Show current server state
    renderquery schema                       List available fields and artifact types
    renderquery save-index <path>            Persist L1 cache to file
    renderquery load-index <path>            Load L1 cache from file
    renderquery serve [--host 0.0.0.0] [--port 8080]  Start HTTP server

Query plan JSON format (see QueryPlan.from_json):
    {
        "source": {"kind": "actions", "params": {"flags": 2}},
        "steps": [
            {"op": "with_counter", "params": {"counter": 1}},
            {"op": "sort", "params": {"field": "duration_gpu", "desc": true}},
            {"op": "take_percent", "params": {"pct": 10}}
        ],
        "projection": [
            {"name": "event_id", "expr": "{event_id}"},
            {"name": "screenshot", "expr": "screenshot", "is_artifact": true,
             "artifact_params": {"width": 512, "height": 512}}
        ],
        "output_dir": "./out/"
    }

Output: JSON on stdout. Errors go to stderr with exit code 1.
"""

from __future__ import annotations

import sys
import json
import argparse


# ------------------------------------------------------------------ #
# Module-level singleton (for multi-command CLI sessions)
# ------------------------------------------------------------------ #

_client_state: dict = {"instance": None, "capture_path": None}


def _get_client() -> dict:
    return _client_state


# ------------------------------------------------------------------ #
# Main entry point
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(
        prog="renderquery",
        description="Database-like query engine for RenderDoc replay snapshots",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # load
    p_load = sub.add_parser("load", help="Load a capture file")
    p_load.add_argument("capture", help="Path to .rdc capture file")

    # query
    p_query = sub.add_parser("query", help="Execute a query plan")
    p_query.add_argument(
        "--plan", default=None,
        help="Query plan JSON string (if omitted, read from stdin)",
    )
    p_query.add_argument(
        "--capture", default=None,
        help="Capture file to load (if not already loaded)",
    )
    p_query.add_argument(
        "--output-dir", default=None,
        help="Output directory for materialized artifacts (default: ./out/)",
    )

    # status
    sub.add_parser("status", help="Show current state")

    # schema
    sub.add_parser("schema", help="List available fields and artifact types")

    # save-index
    p_save = sub.add_parser("save-index", help="Persist L1 cache to file")
    p_save.add_argument("path", help="Output JSON file path")

    # load-index
    p_loadidx = sub.add_parser("load-index", help="Load L1 cache from file")
    p_loadidx.add_argument("path", help="Input JSON file path")

    # serve
    p_serve = sub.add_parser("serve", help="Start HTTP server")
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind address")
    p_serve.add_argument("--port", type=int, default=8080, help="Listen port")
    p_serve.add_argument("--capture", default=None, help="Capture to load on startup")

    args = parser.parse_args()
    state = _get_client()

    if args.command == "load":
        _cmd_load(args.capture, state)
    elif args.command == "query":
        _cmd_query(args, state)
    elif args.command == "status":
        _cmd_status(state)
    elif args.command == "schema":
        _cmd_schema()
    elif args.command == "save-index":
        _cmd_save_index(args.path, state)
    elif args.command == "load-index":
        _cmd_load_index(args.path, state)
    elif args.command == "serve":
        _cmd_serve(args)


# ------------------------------------------------------------------ #
# Commands
# ------------------------------------------------------------------ #

def _cmd_load(capture_path: str, state: dict) -> None:
    if state["instance"] is not None:
        state["instance"].shutdown()
        state["instance"] = None

    from renderquery.sdk import RenderQueryClient

    try:
        state["instance"] = RenderQueryClient(capture_path)
        state["capture_path"] = capture_path
        _output_ok({"loaded": capture_path})
    except Exception as e:
        _output_error(f"Failed to load capture: {e}")
        sys.exit(1)


def _cmd_query(args, state: dict) -> None:
    # Ensure a capture is loaded
    if state["instance"] is None:
        if args.capture:
            _cmd_load(args.capture, state)
            if state["instance"] is None:
                sys.exit(1)
        else:
            _output_error("No capture loaded. Use 'load' first or --capture.")
            sys.exit(1)

    # Read plan JSON from --plan arg or stdin
    plan_json = args.plan
    if plan_json is None:
        plan_json = sys.stdin.read()

    if not plan_json.strip():
        _output_error("No query plan provided. Use --plan or pipe JSON via stdin.")
        sys.exit(1)

    from renderquery.engine.plan import QueryPlan
    from renderquery.engine.executor import ExecutorBusy

    try:
        plan = QueryPlan.from_json(plan_json)
    except Exception as e:
        _output_error(f"Invalid query plan JSON: {e}")
        sys.exit(1)

    output_dir = args.output_dir or plan.output_dir or "./out/"

    try:
        results = state["instance"]._executor.execute(plan, output_dir)
        _output_ok(results)
    except ExecutorBusy:
        _output_error("Executor is busy")
        sys.exit(1)
    except Exception as e:
        _output_error(f"Query execution failed: {e}")
        sys.exit(1)


def _cmd_status(state: dict) -> None:
    if state["instance"] is None:
        _output_ok({"loaded": False, "busy": False, "capture_path": None})
    else:
        _output_ok({
            "loaded": True,
            "busy": state["instance"].is_busy,
            "capture_path": state["capture_path"],
        })


def _cmd_schema() -> None:
    _output_ok({
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
    })


def _cmd_save_index(path: str, state: dict) -> None:
    if state["instance"] is None:
        _output_error("No capture loaded")
        sys.exit(1)
    try:
        state["instance"].save_index(path)
        _output_ok({"saved": path})
    except Exception as e:
        _output_error(f"Failed to save index: {e}")
        sys.exit(1)


def _cmd_load_index(path: str, state: dict) -> None:
    if state["instance"] is None:
        _output_error("No capture loaded")
        sys.exit(1)
    try:
        state["instance"].load_index(path)
        _output_ok({"loaded": path})
    except Exception as e:
        _output_error(f"Failed to load index: {e}")
        sys.exit(1)


def _cmd_serve(args) -> None:
    from .http_server import run_server
    run_server(host=args.host, port=args.port, capture_path=args.capture)


# ------------------------------------------------------------------ #
# Output helpers
# ------------------------------------------------------------------ #

def _output_ok(data) -> None:
    print(json.dumps(data, indent=2, default=str))


def _output_error(msg: str) -> None:
    print(json.dumps({"error": msg}), file=sys.stderr)
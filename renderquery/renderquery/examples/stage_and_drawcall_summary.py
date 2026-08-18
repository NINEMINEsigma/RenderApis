"""Example: Export per-stage (marker) summary + per-drawcall detail to a two-sheet Excel.

Sheet "Stages":    one row per marker (stage) at every nesting level, with the
                   GPU/CPU duration of the whole marker range and a screenshot
                   of the frame state at the stage's last drawcall.
Sheet "Drawcalls": one row per drawcall with its owning stage path, screenshots
                   and mesh artifacts (same set as all_gpu_drawcall_screenshots).

Usage:
    python -m renderquery.examples.stage_and_drawcall_summary <capture.rdc> [--output-dir ./out/]
"""

import os
import argparse

import renderdoc as rd

from renderquery.sdk import RenderQueryClient
from renderquery.engine import artifacts
from renderquery.examples.xlsx_helpers import write_summary_xlsx

_MARKER_FLAGS = int(rd.ActionFlags.PushMarker) | int(rd.ActionFlags.SetMarker)


def main():
    parser = argparse.ArgumentParser(description="Stage summary + drawcall detail export")
    parser.add_argument("capture", help="Path to .rdc capture file")
    parser.add_argument("--output-dir", default="./out/", help="Output directory for artifacts")
    args = parser.parse_args()

    print(f"Opening capture: {args.capture}")
    client = RenderQueryClient(args.capture)

    print("Querying stages (marker ranges)...")
    stage_query = (client.query()
        .from_events()
        .filter(f"flags & {_MARKER_FLAGS}")
        .with_gpu_counter(int(rd.GPUCounter.EventGPUDuration))
        .project(
            event_range="{event_range}",
            stage_path="{stage_path}",
            depth="{depth}",
            duration_gpu="{duration_gpu}",
            duration_cpu="{duration_cpu}",
            screenshot=artifacts.screenshot(width=512, height=512),
        )
        .to_file(args.output_dir))
    stage_rows = client.execute(stage_query, args.output_dir)

    print(f"Got {len(stage_rows)} stages. Querying drawcalls...")
    drawcall_query = (client.query()
        .from_actions(flags=int(rd.ActionFlags.Drawcall))
        .with_gpu_counter(int(rd.GPUCounter.EventGPUDuration))
        .sort_by("duration_gpu", desc=True)
        .project(
            event_id="{event_id}",
            name="{name}",
            stage_name="{stage_path}",
            duration_gpu="{duration_gpu}",
            duration_cpu="{duration_cpu}",
            num_indices="{num_indices}",
            num_instances="{num_instances}",
            screenshot=artifacts.screenshot(width=512, height=512, overlay="Drawcall"),
            mesh_screenshot=artifacts.mesh_screenshot(width=512, height=512, stage="PreVS"),
            mesh=artifacts.mesh(stage="PreVS"),
            log=artifacts.log(filetype="txt"),
        )
        .to_file(args.output_dir))
    drawcall_rows = client.execute(drawcall_query, args.output_dir)

    print(f"\nGot {len(drawcall_rows)} drawcalls. Stages (tree order):\n")
    for r in stage_rows:
        dur = r.get("duration_gpu")
        dur_str = f"{dur:.3f}us" if dur is not None else "N/A"
        indent = "  " * (r.get("depth") or 0)
        print(f"  {indent}{r['stage_path']} | GPU {dur_str}")

    xlsx_path = os.path.join(args.output_dir, "summary.xlsx")
    write_summary_xlsx(xlsx_path, [
        {
            "title": "Stages",
            "headers": ["EID Range", "Stage Path", "Depth",
                        "GPU Duration (GPU执行耗时, us)", "CPU Duration (API提交耗时, us)",
                        "Screenshot"],
            "fields": ["event_range", "stage_path", "depth", "duration_gpu", "duration_cpu",
                       "screenshot"],
            "widths": [12, 50, 8, 28, 28, 30],
            "rows": stage_rows,
            "image_fields": {"screenshot": "Screenshot"},
        },
        {
            "title": "Drawcalls",
            "headers": ["Event ID", "Name", "Stage",
                        "GPU Duration (GPU执行耗时, us)", "CPU Duration (API提交耗时, us)",
                        "Num Indices", "DC Screenshot", "Mesh Screenshot"],
            "fields": ["event_id", "name", "stage_name", "duration_gpu", "duration_cpu",
                       "num_indices", "screenshot", "mesh_screenshot"],
            "widths": [12, 40, 40, 28, 28, 12, 30, 30],
            "rows": drawcall_rows,
            "image_fields": {"screenshot": "DC Screenshot",
                             "mesh_screenshot": "Mesh Screenshot"},
        },
    ])
    print(f"\nSummary Excel: {xlsx_path}")

    client.shutdown()
    print("Done.")


if __name__ == "__main__":
    main()
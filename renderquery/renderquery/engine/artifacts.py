"""Artifact descriptors — declarative specs for binary materialization.

These are *not* the artifacts themselves, only descriptions of what the Executor
should produce. Each descriptor is a lightweight dataclass that gets embedded
in a Projection's ``artifact_params`` and serialized into the QueryPlan IR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ArtifactSpec:
    """Base class for all artifact specifications."""

    kind: str  # "screenshot" | "mesh" | "texture_data" | "shader_disasm"
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"kind": self.kind, **self.params}


def screenshot(
    width: int = 0,
    height: int = 0,
    filetype: str = "png",
    texture_id: str | None = None,
    mip: int = 0,
    slice: int = 0,
    sample: int = 0,
) -> ArtifactSpec:
    """Describe a screenshot artifact.

    By default captures the current color output target at the event.
    If ``texture_id`` is provided, captures that specific texture instead.

    Args:
        width:  Target width in pixels. 0 = original size.
        height: Target height in pixels. 0 = original size.
        filetype: Output format — "png", "jpg", "tga", "bmp".
        texture_id: ResourceId string for a specific texture, or None for output target.
        mip: Mip level to capture.
        slice: Array slice to capture.
        sample: MSAA sample index.
    """
    return ArtifactSpec(
        kind="screenshot",
        params={
            "width": width,
            "height": height,
            "filetype": filetype,
            "texture_id": texture_id,
            "mip": mip,
            "slice": slice,
            "sample": sample,
        },
    )


def mesh(
    stage: str = "PostVS",
    instance: int = 0,
    view: int = 0,
    format: str = "obj",
) -> ArtifactSpec:
    """Describe a mesh artifact — post-transform vertex data exported to a file.

    Args:
        stage: Which geometry stage to extract — "PostVS", "PostGS", "PostMesh", "TaskOut".
        instance: Instance index for instanced draws.
        view: Multiview view index.
        format: Output format — "obj" or "glb".
    """
    return ArtifactSpec(
        kind="mesh",
        params={
            "stage": stage,
            "instance": instance,
            "view": view,
            "format": format,
        },
    )


def texture_data(
    resource_id: str,
    mip: int = 0,
    slice: int = 0,
    sample: int = 0,
    filetype: str = "dds",
) -> ArtifactSpec:
    """Describe raw texture data extraction.

    Args:
        resource_id: ResourceId string of the texture.
        mip: Mip level.
        slice: Array slice.
        sample: MSAA sample index.
        filetype: Output format — "dds", "png", "tga", "bmp".
    """
    return ArtifactSpec(
        kind="texture_data",
        params={
            "resource_id": resource_id,
            "mip": mip,
            "slice": slice,
            "sample": sample,
            "filetype": filetype,
        },
    )


def shader_disasm(
    stage: str = "Vertex",
    target: str = "",
) -> ArtifactSpec:
    """Describe shader disassembly extraction.

    Args:
        stage: Shader stage — "Vertex", "Pixel", "Geometry", "Hull", "Domain",
              "Compute", "Mesh", "Amplification".
        target: Disassembly target name (from GetDisassemblyTargets), or "" for default.
    """
    return ArtifactSpec(
        kind="shader_disasm",
        params={
            "stage": stage,
            "target": target,
        },
    )


def buffer_data(
    resource_id: str,
    offset: int = 0,
    length: int = 0,
) -> ArtifactSpec:
    """Describe raw buffer data extraction.

    Args:
        resource_id: ResourceId string of the buffer.
        offset: Byte offset to start reading from.
        length: Number of bytes to read, or 0 for the rest of the buffer.
    """
    return ArtifactSpec(
        kind="buffer_data",
        params={
            "resource_id": resource_id,
            "offset": offset,
            "length": length,
        },
    )


def mesh_screenshot(
    width: int = 512,
    height: int = 512,
    stage: str = "PostVS",
    instance: int = 0,
    view: int = 0,
    wireframe: bool = True,
    filetype: str = "png",
) -> ArtifactSpec:
    """Describe a mesh screenshot — render the drawcall's mesh with highlight via ReplayOutput.

    Args:
        width: Output image width in pixels.
        height: Output image height in pixels.
        stage: Which geometry stage — "PostVS", "PostGS", "PostMesh", "TaskOut".
        instance: Instance index for instanced draws.
        view: Multiview view index.
        wireframe: True to render wireframe overlay.
        filetype: Output format — "png", "jpg".
    """
    return ArtifactSpec(
        kind="mesh_screenshot",
        params={
            "width": width,
            "height": height,
            "stage": stage,
            "instance": instance,
            "view": view,
            "wireframe": wireframe,
            "filetype": filetype,
        },
    )


def log(filetype: str = "txt") -> ArtifactSpec:
    """Describe a detailed log file artifact.

    Args:
        filetype: Output format — "txt" or "json".
    """
    return ArtifactSpec(
        kind="log",
        params={"filetype": filetype},
    )


def excel(filetype: str = "csv") -> ArtifactSpec:
    """Describe an Excel/table export artifact.

    Args:
        filetype: Output format — "csv" (no dependency) or "xlsx" (requires openpyxl).
    """
    return ArtifactSpec(
        kind="excel",
        params={"filetype": filetype},
    )
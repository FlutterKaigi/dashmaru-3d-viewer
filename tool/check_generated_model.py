#!/usr/bin/env python3
"""Compare distributed and regenerated models without overwriting either asset.

Python versions and platform math libraries can produce different final float
digits. Only JSON floats and declared float32 accessors receive a tolerance;
structure, integer accessors, metadata, and other binary bytes remain exact.
"""

import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile


ABS_TOL = 1e-7
REL_TOL = 1e-6
GENERATORS = (
    "build_dashmaru.py",
    "dashmaru_expressions.py",
    "dashmaru_materials.py",
)
COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4,
          "MAT2": 4, "MAT3": 9, "MAT4": 16}


class ModelMismatch(ValueError):
    """The delivered model and its generator no longer describe the same data."""


def require(condition, message):
    if not condition:
        raise ModelMismatch(message)


def compare_float(expected, actual, location):
    require(
        math.isfinite(expected) and math.isfinite(actual),
        f"{location}: non-finite float",
    )
    require(
        math.isclose(expected, actual, rel_tol=REL_TOL, abs_tol=ABS_TOL),
        f"{location}: {expected!r} != {actual!r}",
    )


def compare_json(expected, actual, location="JSON"):
    require(type(expected) is type(actual), f"{location}: value type changed")
    if isinstance(expected, dict):
        require(expected.keys() == actual.keys(), f"{location}: object keys changed")
        for key in expected:
            compare_json(expected[key], actual[key], f"{location}.{key}")
    elif isinstance(expected, list):
        require(len(expected) == len(actual), f"{location}: array length changed")
        for index, (before, after) in enumerate(zip(expected, actual)):
            compare_json(before, after, f"{location}[{index}]")
    elif isinstance(expected, float):
        compare_float(expected, actual, location)
    else:
        require(expected == actual, f"{location}: {expected!r} != {actual!r}")


def read_glb(data):
    require(len(data) >= 12, "GLB: truncated header")
    magic, version, total = struct.unpack_from("<4sII", data)
    require(magic == b"glTF" and version == 2, "GLB: expected glTF 2")
    require(total == len(data), "GLB: incorrect total byte length")
    chunks = []
    offset = 12
    while offset < total:
        require(offset + 8 <= total, "GLB: truncated chunk header")
        size, kind = struct.unpack_from("<I4s", data, offset)
        offset += 8
        require(size % 4 == 0 and offset + size <= total, "GLB: invalid chunk size")
        chunks.append((kind, data[offset:offset + size]))
        offset += size
    require(
        [kind for kind, _ in chunks] == [b"JSON", b"BIN\x00"],
        "GLB: expected one JSON chunk followed by one BIN chunk",
    )
    return json.loads(chunks[0][1]), chunks[1][1]


def integer(value, location, minimum=0):
    require(type(value) is int and value >= minimum, f"{location}: invalid integer")
    return value


def accessor_spans(doc, binary_length):
    """Return actual accessor byte spans, preserving interleaved gaps as strict."""
    buffers = doc["buffers"]
    require(len(buffers) == 1 and "uri" not in buffers[0], "GLB: external buffers unsupported")
    buffer_size = integer(buffers[0]["byteLength"], "buffer.byteLength")
    require(0 <= binary_length - buffer_size <= 3, "GLB: invalid BIN padding")
    float_spans, integer_spans = [], []
    for index, accessor in enumerate(doc["accessors"]):
        label = f"accessors[{index}]"
        require("sparse" not in accessor, f"{label}: sparse accessors unsupported")
        view_index = integer(accessor["bufferView"], f"{label}.bufferView")
        view = doc["bufferViews"][view_index]
        require(type(view["buffer"]) is int and view["buffer"] == 0,
                f"{label}: expected embedded buffer 0")
        view_offset = integer(view.get("byteOffset", 0), f"{label}.view.byteOffset")
        view_size = integer(view["byteLength"], f"{label}.view.byteLength")
        require(view_offset + view_size <= buffer_size, f"{label}: view outside buffer")
        component = integer(accessor["componentType"], f"{label}.componentType")
        require(component in COMPONENT_BYTES, f"{label}: unknown component type")
        kind = accessor["type"]
        require(kind in WIDTHS, f"{label}: unknown accessor type")
        component_size = COMPONENT_BYTES[component]
        element_size = component_size * WIDTHS[kind]
        if kind.startswith("MAT"):
            columns = int(kind[-1])
            element_size = columns * ((columns * component_size + 3) // 4 * 4)
        count = integer(accessor["count"], f"{label}.count", minimum=1)
        relative = integer(accessor.get("byteOffset", 0), f"{label}.byteOffset")
        stride = integer(view.get("byteStride", element_size), f"{label}.stride")
        require(stride >= element_size and stride % component_size == 0,
                f"{label}: invalid stride")
        require((view_offset + relative) % component_size == 0,
                f"{label}: unaligned accessor")
        require(relative + (count - 1) * stride + element_size <= view_size,
                f"{label}: accessor outside view")
        spans = float_spans if component == 5126 else integer_spans
        start = view_offset + relative
        if stride == element_size:
            spans.append((start, start + count * stride, label))
        else:
            spans.extend((start + row * stride, start + row * stride + element_size, label)
                         for row in range(count))
    return float_spans, integer_spans


def compare_glb(expected, actual):
    expected_doc, expected_bin = read_glb(expected)
    actual_doc, actual_bin = read_glb(actual)
    compare_json(expected_doc, actual_doc)
    require(len(expected_bin) == len(actual_bin), "BIN: byte length changed")
    float_spans, integer_spans = accessor_spans(expected_doc, len(expected_bin))
    tolerant = bytearray(len(expected_bin))
    for start, end, _ in float_spans:
        tolerant[start:end] = b"\x01" * (end - start)
    # An integer view overlapping a float view must still be byte-for-byte equal.
    for start, end, _ in integer_spans:
        tolerant[start:end] = b"\x00" * (end - start)
    for offset, (before, after, allowed) in enumerate(zip(expected_bin, actual_bin, tolerant)):
        if not allowed and before != after:
            raise ModelMismatch(f"BIN[{offset}]: non-float byte changed")
    for start, end, label in float_spans:
        before = struct.iter_unpack("<f", expected_bin[start:end])
        after = struct.iter_unpack("<f", actual_bin[start:end])
        for index, ((a,), (b,)) in enumerate(zip(before, after)):
            compare_float(a, b, f"{label}.float[{index}]")


def compare_assets(expected_directory, actual_directory):
    expected_glb = (expected_directory / "dashmaru.glb").read_bytes()
    actual_glb = (actual_directory / "dashmaru.glb").read_bytes()
    compare_glb(expected_glb, actual_glb)
    manifests = []
    for directory, data in ((expected_directory, expected_glb), (actual_directory, actual_glb)):
        manifest = json.loads((directory / "dashmaru_manifest.json").read_text(encoding="utf-8"))
        size = integer(manifest.pop("bytes"), "manifest.bytes")
        require(size == len(data), f"{directory.name}: manifest.bytes disagrees with GLB")
        manifests.append(manifest)
    # JSON float spelling can change the GLB's serialized size. Each manifest
    # must report its own correct size; all other integer fields remain exact.
    compare_json(*manifests, location="manifest")


def check_generated_model(repository):
    with tempfile.TemporaryDirectory(prefix="dashmaru-generated-") as temporary:
        destination = Path(temporary)
        scripts = destination / "tool"
        scripts.mkdir()
        for name in GENERATORS:
            shutil.copy2(repository / "tool" / name, scripts / name)
        subprocess.run(
            [sys.executable, str(scripts / "build_dashmaru.py")],
            cwd=destination, check=True, capture_output=True, text=True,
        )
        compare_assets(repository / "assets/models", destination / "assets/models")


def main():
    try:
        check_generated_model(Path(__file__).resolve().parents[1])
    except subprocess.CalledProcessError as error:
        print(f"FAIL: model generation failed\n{error.stderr}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, IndexError, TypeError, struct.error) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: generated model matches distributed assets (float abs={ABS_TOL:g}, rel={REL_TOL:g}).")
    print("  Structure, metadata, integer values and non-float binary bytes match exactly.")
    print("  Distributed files were not overwritten.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

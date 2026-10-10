#!/usr/bin/env python3
"""Check the exported model and its animation contract without third-party tools.

Run from any directory: python3 path/to/tool/check_dashmaru.py [path/to/model.glb]
This checks the delivered binary, independently of the model-building code. It is
not a replacement for watching all thirteen gestures in Flutter Scene. An optional
--baseline model.glb checks gait timing and the established upper-body Walk pose.
Use --preserve-existing model.glb to verify every key of the original eight clips.
Use --subframes 3 to also check three interpolated poses between every baked key.
"""

import argparse
import json
import math
from pathlib import Path
import struct
import sys

from check_dashmaru_surfaces import check_surface_quality


ESTABLISHED_CLIPS = frozenset(
    {"Idle", "Walk", "Run", "Jump", "Wave", "Blink", "Shake", "Sit"}
)
EXTRA_GESTURES = frozenset({"Nod", "Tilt", "Bow", "Celebrate", "Stretch"})


class InvalidModel(Exception):
    """An exported asset violates a required model or animation invariant."""


def require(condition, message):
    if not condition:
        raise InvalidModel(message)


def finite_json(value, location="JSON"):
    if isinstance(value, float):
        require(math.isfinite(value), f"{location}: non-finite number")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            finite_json(item, f"{location}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            finite_json(item, f"{location}.{key}")


def close(a, b):
    return len(a) == len(b) and all(
        math.isclose(x, y, rel_tol=1e-5, abs_tol=1e-6) for x, y in zip(a, b)
    )


def same_pose(a, b, path):
    # q and -q represent the same orientation.
    return close(a, b) or (path == "rotation" and close(a, tuple(-v for v in b)))


def interpolate(a, b, fraction, path, mode="LINEAR"):
    """Match glTF TRS interpolation, including Flutter Scene's short-arc SLERP."""
    if mode == "STEP":
        return a
    if path != "rotation":
        return tuple(x + (y - x) * fraction for x, y in zip(a, b))
    cosine = sum(x * y for x, y in zip(a, b))
    if cosine < 0:
        b, cosine = tuple(-value for value in b), -cosine
    if cosine >= 0.999:
        value = tuple(x + (y - x) * fraction for x, y in zip(a, b))
        length = math.sqrt(sum(v * v for v in value))
        return tuple(v / length for v in value)
    sine = math.sqrt(1 - cosine * cosine)
    angle = math.atan2(sine, cosine)
    before = math.sin((1 - fraction) * angle) / sine
    after = math.sin(fraction * angle) / sine
    return tuple(x * before + y * after for x, y in zip(a, b))


def sampled_poses(tracks, subframes, modes):
    count = len(next(iter(tracks.values())))
    for frame in range(count):
        yield frame, {key: rows[frame] for key, rows in tracks.items()}
        if frame + 1 == count:
            break
        for subframe in range(1, subframes + 1):
            fraction = subframe / (subframes + 1)
            yield (
                frame + fraction,
                {
                    key: interpolate(
                        rows[frame], rows[frame + 1], fraction, key[1], modes[key]
                    )
                    for key, rows in tracks.items()
                },
            )


IDENTITY = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)


def multiply(a, b):
    """Multiply glTF's column-major matrices without importing the exporter."""
    return tuple(
        sum(a[row + k * 4] * b[k + column * 4] for k in range(4))
        for column in range(4)
        for row in range(4)
    )


def node_matrix(node):
    if "matrix" in node:
        matrix = node["matrix"]
        require(len(matrix) == 16, "Node matrix must contain 16 values")
        require(
            not any(key in node for key in ("translation", "rotation", "scale")),
            "Node cannot contain both matrix and TRS transforms",
        )
        return tuple(matrix)
    translation = node.get("translation", (0, 0, 0))
    rotation = node.get("rotation", (0, 0, 0, 1))
    scale = node.get("scale", (1, 1, 1))
    require(
        len(translation) == len(scale) == 3 and len(rotation) == 4,
        "Node has malformed TRS transforms",
    )
    require(
        math.isclose(sum(v * v for v in rotation), 1, abs_tol=1e-5),
        "Node has a non-unit default quaternion",
    )
    x, y, z, w = rotation
    sx, sy, sz = scale
    return (
        (1 - 2 * (y * y + z * z)) * sx,
        2 * (x * y + z * w) * sx,
        2 * (x * z - y * w) * sx,
        0,
        2 * (x * y - z * w) * sy,
        (1 - 2 * (x * x + z * z)) * sy,
        2 * (y * z + x * w) * sy,
        0,
        2 * (x * z + y * w) * sz,
        2 * (y * z - x * w) * sz,
        (1 - 2 * (x * x + y * y)) * sz,
        0,
        *translation,
        1,
    )


class Model:
    COMPONENTS = {
        5120: ("b", 1),
        5121: ("B", 1),
        5122: ("h", 2),
        5123: ("H", 2),
        5125: ("I", 4),
        5126: ("f", 4),
    }
    WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

    def __init__(self, path):
        blob = path.read_bytes()
        require(len(blob) >= 20, "GLB is too short")
        magic, version, length = struct.unpack_from("<4sII", blob)
        require(magic == b"glTF" and version == 2, "Expected glTF 2.0 binary")
        require(length == len(blob), "GLB header length does not match file")
        chunks = []
        offset = 12
        while offset < length:
            require(offset + 8 <= length, "Truncated GLB chunk header")
            size, kind = struct.unpack_from("<I4s", blob, offset)
            require(size % 4 == 0, "GLB chunk is not four-byte aligned")
            offset += 8
            require(offset + size <= length, "GLB chunk extends beyond file")
            chunks.append((kind, blob[offset : offset + size]))
            offset += size
        require(
            [kind for kind, _ in chunks] == [b"JSON", b"BIN\x00"],
            "Expected one JSON chunk followed by one embedded BIN chunk",
        )
        self.doc = json.loads(chunks[0][1])
        self.binary = chunks[1][1]
        finite_json(self.doc)
        require(
            self.doc.get("asset", {}).get("version") == "2.0", "Invalid asset version"
        )
        buffers = self.doc.get("buffers", [])
        require(
            len(buffers) == 1 and "uri" not in buffers[0],
            "Model must be self-contained in one embedded buffer",
        )
        self.buffer_length = buffers[0]["byteLength"]
        require(
            0 <= len(self.binary) - self.buffer_length <= 3,
            "BIN size does not match declared buffer and alignment padding",
        )
        self.accessors = self.doc.get("accessors", [])
        self.views = self.doc.get("bufferViews", [])
        self.nodes = self.doc.get("nodes", [])
        self.cache = {}
        for index, view in enumerate(self.views):
            start, size = view.get("byteOffset", 0), view["byteLength"]
            require(view["buffer"] == 0, f"bufferView {index}: invalid buffer")
            require(
                start >= 0 and size > 0 and start + size <= self.buffer_length,
                f"bufferView {index}: invalid binary bounds",
            )
        for index in range(len(self.accessors)):
            self.read(index)

    def read(self, index):
        if index in self.cache:
            return self.cache[index]
        require(
            isinstance(index, int) and 0 <= index < len(self.accessors),
            f"Invalid accessor index: {index}",
        )
        accessor = self.accessors[index]
        label = f"accessor {index}"
        require(
            "sparse" not in accessor,
            f"{label}: sparse data is outside this model contract",
        )
        view_index = accessor["bufferView"]
        require(0 <= view_index < len(self.views), f"{label}: invalid bufferView")
        view = self.views[view_index]
        component = accessor["componentType"]
        require(component in self.COMPONENTS, f"{label}: invalid component type")
        require(
            accessor["type"] in self.WIDTHS,
            f"{label}: unsupported accessor shape",
        )
        require(
            accessor["type"] != "MAT4" or component == 5126,
            f"{label}: inverse-bind matrices must contain floats",
        )
        fmt, unit = self.COMPONENTS[component]
        width = self.WIDTHS[accessor["type"]]
        packed = width * unit
        stride = view.get("byteStride", packed)
        start, count = accessor.get("byteOffset", 0), accessor["count"]
        require(
            count > 0 and start >= 0 and stride >= packed and stride % unit == 0,
            f"{label}: invalid count, offset, or stride",
        )
        absolute = view.get("byteOffset", 0) + start
        require(absolute % unit == 0, f"{label}: misaligned component")
        require(
            start + (count - 1) * stride + packed <= view["byteLength"],
            f"{label}: data exceeds its bufferView",
        )
        values = [
            struct.unpack_from("<" + fmt * width, self.binary, absolute + i * stride)
            for i in range(count)
        ]
        require(
            all(math.isfinite(value) for row in values for value in row),
            f"{label}: contains NaN or infinity",
        )
        for bound, operation in (("min", min), ("max", max)):
            if bound in accessor:
                actual = tuple(
                    operation(row[axis] for row in values) for axis in range(width)
                )
                require(
                    close(accessor[bound], actual),
                    f"{label}: incorrect declared {bound}",
                )
        self.cache[index] = values
        return values

    def check_meshes(self):
        meshes = self.doc.get("meshes", [])
        require(meshes, "Model contains no geometry")
        triangles = 0
        for mesh_index, mesh in enumerate(meshes):
            for primitive in mesh["primitives"]:
                label = f"mesh {mesh_index} ({mesh.get('name', 'unnamed')})"
                attributes = primitive["attributes"]
                require("POSITION" in attributes, f"{label}: no positions")
                positions = self.read(attributes["POSITION"])
                require(
                    self.accessors[attributes["POSITION"]]["type"] == "VEC3",
                    f"{label}: positions must be VEC3",
                )
                for semantic, accessor in attributes.items():
                    require(
                        len(self.read(accessor)) == len(positions),
                        f"{label}: {semantic} count differs from positions",
                    )
                require(primitive.get("mode", 4) == 4, f"{label}: expected triangles")
                if "indices" in primitive:
                    accessor = self.accessors[primitive["indices"]]
                    require(
                        accessor["type"] == "SCALAR"
                        and accessor["componentType"] in (5121, 5123, 5125),
                        f"{label}: invalid index format",
                    )
                    indices = self.read(primitive["indices"])
                    require(
                        all(0 <= row[0] < len(positions) for row in indices),
                        f"{label}: vertex index out of bounds",
                    )
                    count = len(indices)
                else:
                    count = len(positions)
                require(count % 3 == 0, f"{label}: incomplete triangle")
                triangles += count // 3
        for index, node in enumerate(self.nodes):
            require(
                all(value > 0 for value in node.get("scale", [1, 1, 1])),
                f"node {index}: non-positive default scale",
            )
            if "mesh" in node:
                require(0 <= node["mesh"] < len(meshes), f"node {index}: invalid mesh")
            require(
                all(0 <= child < len(self.nodes) for child in node.get("children", [])),
                f"node {index}: invalid child",
            )
        return len(meshes), triangles

    def check_bib_clearance(self):
        # Check exported triangle interiors, not just their projected vertices:
        # a coarse chord can cut into the belly even when every vertex clears it.
        meshes = {mesh["name"]: mesh for mesh in self.doc["meshes"]}
        require("Body" in meshes and "White bib" in meshes, "Missing body or bib")
        body = meshes["Body"]["primitives"][0]
        positions = self.read(body["attributes"]["POSITION"])
        lower = [min(vertex[axis] for vertex in positions) for axis in range(3)]
        upper = [max(vertex[axis] for vertex in positions) for axis in range(3)]
        center = [(lo + hi) / 2 for lo, hi in zip(lower, upper)]
        radii = [(hi - lo) / 2 for lo, hi in zip(lower, upper)]
        require(all(radius > 0 for radius in radii), "Body has no ellipsoid volume")
        bib = meshes["White bib"]["primitives"][0]
        vertices = self.read(bib["attributes"]["POSITION"])
        indices = [row[0] for row in self.read(bib["indices"])]
        minimum = math.inf
        for start in range(0, len(indices), 3):
            triangle = [vertices[index] for index in indices[start : start + 3]]
            for weights in (
                (0.5, 0.5, 0),
                (0.5, 0, 0.5),
                (0, 0.5, 0.5),
                (1 / 3, 1 / 3, 1 / 3),
            ):
                x, y, z = (
                    sum(
                        vertex[axis] * weight
                        for vertex, weight in zip(triangle, weights)
                    )
                    for axis in range(3)
                )
                radial = ((x - center[0]) / radii[0]) ** 2 + (
                    (y - center[1]) / radii[1]
                ) ** 2
                body_z = center[2] + radii[2] * math.sqrt(max(0, 1 - radial))
                clearance = z - body_z
                minimum = min(minimum, clearance)
                require(
                    clearance > -0.001,
                    f"White bib triangle {start // 3} cuts into the body "
                    f"(sampled gap {clearance:.6f})",
                )
        return (
            f"White bib triangle interiors clear the body (minimum gap {minimum:.6f})"
        )

    def world_matrices(self, overrides=None):
        parents = {}
        for parent, node in enumerate(self.nodes):
            for child in node.get("children", []):
                require(child not in parents, f"node {child}: multiple parents")
                parents[child] = parent
        worlds, visiting = {}, set()

        def visit(index):
            if index in worlds:
                return worlds[index]
            require(index not in visiting, "Node hierarchy contains a cycle")
            visiting.add(index)
            node = dict(self.nodes[index])
            if overrides:
                for (target, path), value in overrides.items():
                    if target == index:
                        node[path] = value
            parent = visit(parents[index]) if index in parents else IDENTITY
            worlds[index] = multiply(parent, node_matrix(node))
            visiting.remove(index)
            return worlds[index]

        for index in range(len(self.nodes)):
            visit(index)
        return worlds

    def check_skins(self):
        skins = self.doc.get("skins", [])
        require(skins, "Model must contain a deformable skeleton")
        worlds = self.world_matrices()
        inverse_binds = {}
        for index, skin in enumerate(skins):
            label = f"skin {index}"
            joints = skin.get("joints", [])
            require(
                joints and len(joints) == len(set(joints)), f"{label}: invalid joints"
            )
            require(
                all(
                    isinstance(joint, int) and 0 <= joint < len(self.nodes)
                    for joint in joints
                ),
                f"{label}: joint index is out of bounds",
            )
            if "skeleton" in skin:
                require(
                    0 <= skin["skeleton"] < len(self.nodes),
                    f"{label}: invalid skeleton root",
                )
            require("inverseBindMatrices" in skin, f"{label}: missing inverse binds")
            accessor = self.accessors[skin["inverseBindMatrices"]]
            require(
                accessor["type"] == "MAT4" and accessor["componentType"] == 5126,
                f"{label}: inverse binds must be floating-point MAT4",
            )
            matrices = self.read(skin["inverseBindMatrices"])
            require(
                len(matrices) == len(joints),
                f"{label}: inverse bind count differs from joints",
            )
            for matrix in matrices:
                require(
                    close((matrix[3], matrix[7], matrix[11], matrix[15]), (0, 0, 0, 1)),
                    f"{label}: inverse bind is not an affine transform",
                )
                determinant = (
                    matrix[0] * (matrix[5] * matrix[10] - matrix[9] * matrix[6])
                    - matrix[4] * (matrix[1] * matrix[10] - matrix[9] * matrix[2])
                    + matrix[8] * (matrix[1] * matrix[6] - matrix[5] * matrix[2])
                )
                require(abs(determinant) > 1e-8, f"{label}: singular inverse bind")
            inverse_binds[index] = matrices

        deformed = {"body": 0, "wing": 0, "leg": 0, "foot": 0}
        blended_vertices = 0
        for node_index, node in enumerate(self.nodes):
            if "mesh" not in node:
                require("skin" not in node, f"node {node_index}: skin without geometry")
                continue
            mesh = self.doc["meshes"][node["mesh"]]
            label = f"node {node_index} ({mesh.get('name', 'unnamed')})"
            for primitive in mesh["primitives"]:
                attributes = primitive["attributes"]
                if "skin" not in node:
                    require(
                        "JOINTS_0" not in attributes and "WEIGHTS_0" not in attributes,
                        f"{label}: skin attributes have no skin",
                    )
                    continue
                skin_index = node["skin"]
                require(0 <= skin_index < len(skins), f"{label}: invalid skin")
                skin = skins[skin_index]
                require(
                    "JOINTS_0" in attributes and "WEIGHTS_0" in attributes,
                    f"{label}: skinned geometry needs joint indices and weights",
                )
                joint_accessor = self.accessors[attributes["JOINTS_0"]]
                weight_accessor = self.accessors[attributes["WEIGHTS_0"]]
                require(
                    joint_accessor["type"] == "VEC4"
                    and joint_accessor["componentType"] in (5121, 5123)
                    and not joint_accessor.get("normalized", False),
                    f"{label}: joint indices must be unsigned byte/short VEC4",
                )
                weight_component = weight_accessor["componentType"]
                require(
                    weight_accessor["type"] == "VEC4"
                    and (
                        weight_component == 5126
                        or (
                            weight_component in (5121, 5123)
                            and weight_accessor.get("normalized", False)
                        )
                    ),
                    f"{label}: weights must be float or normalized unsigned VEC4",
                )
                indices = self.read(attributes["JOINTS_0"])
                weights = self.read(attributes["WEIGHTS_0"])
                divisor = {5121: 255, 5123: 65535, 5126: 1}[weight_component]
                used, blend_count = set(), 0
                for slots, raw in zip(indices, weights):
                    row = tuple(value / divisor for value in raw)
                    require(
                        all(0 <= slot < len(skin["joints"]) for slot in slots),
                        f"{label}: vertex joint index is outside the skin",
                    )
                    require(
                        all(0 <= weight <= 1 for weight in row)
                        and math.isclose(
                            sum(row), 1, abs_tol=2 / divisor if divisor != 1 else 1e-5
                        ),
                        f"{label}: vertex weights must be nonnegative and sum to one",
                    )
                    active = {slot for slot, weight in zip(slots, row) if weight > 1e-4}
                    used.update(active)
                    if len(active) > 1:
                        blend_count += 1
                # A bind-pose error makes parts jump away before animation starts.
                for slot in used:
                    joint = skin["joints"][slot]
                    restored = multiply(worlds[joint], inverse_binds[skin_index][slot])
                    require(
                        close(restored, worlds[node_index]),
                        f"{label}: inverse bind must preserve the default mesh pose",
                    )
                blended_vertices += blend_count
                name = mesh.get("name", "").lower()
                for part in deformed:
                    if (
                        (part in name or (part == "leg" and "shin" in name))
                        and blend_count > 0
                        and len(used) > 1
                    ):
                        deformed[part] += 1
        require(deformed["body"] >= 1, "Body has no vertices blended between bones")
        require(
            deformed["wing"] >= 2, "Both wings must flex across blended bone weights"
        )
        require(deformed["leg"] >= 2, "Both legs must bend across blended bone weights")
        require(
            deformed["foot"] >= 2, "Both feet must flex across blended bone weights"
        )
        return f"{len(skins)} skins; {blended_vertices:,} vertices blend between bones"

    def check_animations(self, subframes=0):
        animations = self.doc.get("animations", [])
        names = [animation.get("name") for animation in animations]
        required = ESTABLISHED_CLIPS | EXTRA_GESTURES
        require(len(names) == len(set(names)), "Animation names are not unique")
        require(
            required <= set(names),
            f"Missing required clips: {sorted(required - set(names))}",
        )
        require(
            set(names) <= required,
            f"Unexpected clips: {sorted(set(names) - required)}",
        )
        defaults = {
            "translation": (0, 0, 0),
            "rotation": (0, 0, 0, 1),
            "scale": (1, 1, 1),
        }
        expected_types = {"translation": "VEC3", "rotation": "VEC4", "scale": "VEC3"}
        clips = {}
        summaries = []
        for animation in animations:
            name = animation["name"]
            tracks, durations, timelines = {}, [], []
            for channel in animation["channels"]:
                target = channel["target"]
                node_index, path = target["node"], target["path"]
                require(
                    0 <= node_index < len(self.nodes), f"{name}: invalid animated node"
                )
                require(
                    path in defaults, f"{name}: unexpected animated property {path}"
                )
                key = (node_index, path)
                require(key not in tracks, f"{name}: duplicate channel target {key}")
                node = self.nodes[node_index]
                label = f"{name}/{node.get('name', node_index)}/{path}"
                require(
                    "matrix" not in node,
                    f"{label}: animated node must use TRS transforms",
                )
                sampler_index = channel["sampler"]
                require(
                    0 <= sampler_index < len(animation["samplers"]),
                    f"{label}: invalid sampler",
                )
                sampler = animation["samplers"][sampler_index]
                require(
                    sampler.get("interpolation", "LINEAR") in ("LINEAR", "STEP"),
                    f"{label}: interpolation must preserve positive scale between keys",
                )
                times = self.read(sampler["input"])
                input_accessor = self.accessors[sampler["input"]]
                require(
                    input_accessor["type"] == "SCALAR"
                    and input_accessor["componentType"] == 5126,
                    f"{label}: timeline must contain floating-point scalars",
                )
                times = [row[0] for row in times]
                require(
                    len(times) >= 2 and abs(times[0]) <= 1e-6,
                    f"{label}: timeline must start at zero and have at least two keys",
                )
                require(
                    all(b > a for a, b in zip(times, times[1:])),
                    f"{label}: timeline is not strictly increasing",
                )
                values = self.read(sampler["output"])
                output_accessor = self.accessors[sampler["output"]]
                require(
                    output_accessor["type"] == expected_types[path]
                    and output_accessor["componentType"] == 5126,
                    f"{label}: invalid output format",
                )
                require(
                    len(values) == len(times),
                    f"{label}: input/output key counts differ",
                )
                if path == "scale":
                    require(
                        all(value > 0 for row in values for value in row),
                        f"{label}: zero/negative scale makes the transform singular",
                    )
                if path == "rotation":
                    require(
                        all(
                            math.isclose(sum(v * v for v in row), 1, abs_tol=1e-5)
                            for row in values
                        ),
                        f"{label}: quaternion is not normalized",
                    )
                neutral = node.get(path, defaults[path])
                if name == "Sit":
                    loop_keys = [
                        i for i, time in enumerate(times) if abs(time - 2.4) <= 1e-5
                    ]
                    require(
                        len(loop_keys) == 1 and abs(times[-1] - 6.4) <= 1e-5,
                        f"{label}: seated loop must run from 2.4 to 6.4 seconds",
                    )
                    require(
                        same_pose(values[0], neutral, path),
                        f"{label}: sitting must begin in the neutral pose",
                    )
                    require(
                        same_pose(values[loop_keys[0]], values[-1], path),
                        f"{label}: seated loop must join matching poses at 2.4 and 6.4 seconds",
                    )
                else:
                    require(
                        same_pose(values[0], values[-1], path),
                        f"{label}: first and last poses must match for a seamless loop",
                    )
                # Locomotion starts inside its gait cycle, avoiding a stop at
                # every repeat. The player blends its fully keyed pose on entry.
                if name not in ("Walk", "Run", "Sit"):
                    require(
                        same_pose(values[0], neutral, path)
                        and same_pose(values[-1], neutral, path),
                        f"{label}: gesture must begin and finish in the neutral pose",
                    )
                tracks[key] = values
                durations.append(times[-1])
                timelines.append(times)
            require(tracks, f"{name}: clip has no channels")
            require(
                max(durations) - min(durations) <= 1e-5,
                f"{name}: tracks do not end together",
            )
            require(
                all(close(timelines[0], timeline) for timeline in timelines),
                f"{name}: baked rig channels must use a common timeline",
            )
            changed = sum(
                not all(same_pose(rows[0], row, key[1]) for row in rows)
                for key, rows in tracks.items()
            )
            require(changed > 0, f"{name}: clip has no actual motion")
            clips[name] = tracks
            summaries.append(
                f"{name}: {max(durations):.2f}s, {len(tracks)} tracks, {changed} moving"
            )

        # Every clip keys every animated property. Omitting another clip's
        # channels leaves stale limbs when the player blends between gestures.
        union = set().union(*(set(tracks) for tracks in clips.values()))
        rig_nodes = {
            joint for skin in self.doc["skins"] for joint in skin["joints"]
        }
        required_rig_tracks = {
            (joint, path)
            for joint in rig_nodes
            for path in ("translation", "rotation", "scale")
        }
        require(
            required_rig_tracks <= union,
            "Every skinned joint needs translation, rotation and scale tracks "
            "so all gestures can restore the complete rig",
        )
        for name, tracks in clips.items():
            require(
                set(tracks) == union,
                f"{name}: missing channels needed to reset another clip's pose",
            )

        named_nodes = {node.get("name"): index for index, node in enumerate(self.nodes)}

        def gesture_track(clip, node_name, path):
            require(
                node_name in named_nodes, f"{clip}: missing gesture node {node_name}"
            )
            key = (named_nodes[node_name], path)
            require(key in clips[clip], f"{clip}: missing {node_name}/{path} channel")
            return clips[clip][key]

        def moves(rows):
            return any(
                max(abs(a - b) for a, b in zip(rows[0], row)) > 1e-3 for row in rows
            )

        def node_moves(clip, node_name):
            require(
                node_name in named_nodes, f"{clip}: missing gesture node {node_name}"
            )
            return any(
                moves(rows)
                for (node, _), rows in clips[clip].items()
                if node == named_nodes[node_name]
            )

        def rotation_component(rows):
            # Track the dominant quaternion vector component, keeping q/-q
            # continuous so representation changes cannot count as flap beats.
            continuous = [rows[0]]
            for row in rows[1:]:
                if sum(a * b for a, b in zip(continuous[-1], row)) < 0:
                    row = tuple(-value for value in row)
                continuous.append(row)
            axis = max(
                range(3),
                key=lambda index: (
                    max(row[index] for row in continuous)
                    - min(row[index] for row in continuous)
                ),
            )
            return axis, [row[axis] for row in continuous]

        for clip in ("Walk", "Run"):
            for leg in ("LeftLeg", "RightLeg"):
                require(
                    moves(gesture_track(clip, leg, "rotation")),
                    f"{clip}: {leg} does not move",
                )
            for knee in ("LeftKnee", "RightKnee"):
                require(
                    moves(gesture_track(clip, knee, "rotation")),
                    f"{clip}: {knee} never bends",
                )
            for side in ("Left", "Right"):
                for joint, minimum in (("Forefoot", 0.20), ("Toe", 0.045)):
                    _, values = rotation_component(
                        gesture_track(clip, side + joint, "rotation")
                    )
                    require(
                        max(values) - min(values) > minimum,
                        f"{clip}: {side}{joint} needs visible, independent sole articulation",
                    )
        run_hips = gesture_track("Run", "Hips", "translation")
        require(
            max(row[0] for row in run_hips) - min(row[0] for row in run_hips) > 0.18,
            "Run: hips must transfer weight visibly between the supporting feet",
        )
        run_torso = gesture_track("Run", "Torso", "rotation")
        run_head = gesture_track("Run", "Head", "rotation")
        require(
            sum(torso[2] * head[2] < 0 for torso, head in zip(run_torso, run_head))
            > len(run_head) * 0.65,
            "Run: the head should counterbalance the sideways body sway",
        )
        jump = gesture_track("Jump", "Dashmaru", "translation")
        require(
            max(row[1] for row in jump) > jump[0][1] + 0.05,
            "Jump: body never visibly leaves its rest height",
        )
        require(
            any(
                moves(gesture_track("Wave", wing, "rotation"))
                for wing in ("LeftWing", "RightWing")
            ),
            "Wave: neither wing moves",
        )
        for wing in ("LeftWing", "RightWing"):
            for clip in ("Jump", "Run"):
                require(
                    moves(gesture_track(clip, wing, "rotation")),
                    f"{clip}: {wing} never flaps",
                )
                bend = gesture_track(clip, wing + "Bend", "rotation")
                axis, values = rotation_component(bend)
                neutral = self.nodes[named_nodes[wing + "Bend"]].get(
                    "rotation", (0, 0, 0, 1)
                )[axis]
                require(
                    min(values) < neutral - 0.04 and max(values) > neutral + 0.04,
                    f"{clip}: {wing} must flex to both sides of its resting bend",
                )
            _, values = rotation_component(gesture_track("Jump", wing, "rotation"))
            directions = [
                1 if b > a else -1
                for a, b in zip(values, values[1:])
                if abs(b - a) > 0.001
            ]
            reversals = sum(a != b for a, b in zip(directions, directions[1:]))
            require(
                max(values) - min(values) > 0.25 and reversals >= 4,
                f"Jump: {wing} must make several visible up/down flap strokes",
            )
        require(
            any(
                moves(gesture_track("Wave", wing, "rotation"))
                for wing in ("LeftWingBend", "RightWingBend")
            ),
            "Wave: neither wing bends",
        )
        require(
            node_moves("Idle", "Torso") and node_moves("Idle", "Head"),
            "Idle: torso and head need visible breathing/secondary motion",
        )
        for part in ("Torso", "Head", "Crest"):
            require(
                node_moves("Shake", part),
                f"Shake: {part} needs visible motion or secondary wobble",
            )
        for part in ("Torso", "Head"):
            rows = gesture_track("Shake", part, "rotation")
            require(
                max(row[2] for row in rows) - min(row[2] for row in rows) > 0.08
                or max(row[1] for row in rows) - min(row[1] for row in rows) > 0.08,
                f"Shake: {part} must visibly sway or turn from side to side",
            )
        sit_hips = gesture_track("Sit", "Hips", "translation")
        require(
            min(row[1] for row in sit_hips) < sit_hips[0][1] - 0.45,
            "Sit: the belly must lower visibly into a seated pose",
        )
        for part in ("Torso", "Head", "Crest", "LeftWing", "RightWing"):
            require(
                node_moves("Sit", part),
                f"Sit: {part} needs a soft settling or breathing movement",
            )
        for eye in ("LeftEye", "RightEye"):
            rows = gesture_track("Blink", eye, "scale")
            require(
                min(row[1] for row in rows) < rows[0][1] * 0.5,
                f"Blink: {eye} does not visibly close",
            )
        summaries.extend(self.check_extra_gestures(clips))
        summaries.extend(self.check_foot_contacts(clips, subframes))
        summaries.append(self.check_sitting_contacts(clips["Sit"], subframes))
        summaries.append(self.check_bow_clearance(clips["Bow"], subframes))
        return summaries

    def check_extra_gestures(self, clips):
        """Assert recognizable directions and amplitudes in exported joint data.

        Loose visual thresholds leave timing and curves to the artist. The
        front-facing Tilt prioritizes keeping the central belly pattern visible
        and rigid over large rotations. Quaternion rotation vectors make
        checks independent of equivalent q/-q representations.
        """
        named = {node.get("name"): index for index, node in enumerate(self.nodes)}

        def track(clip, part, path):
            require(part in named, f"{clip}: missing gesture node {part}")
            key = (named[part], path)
            require(key in clips[clip], f"{clip}: missing {part}/{path} channel")
            return clips[clip][key]

        def rotation_vectors(clip, part):
            vectors = []
            for row in track(clip, part, "rotation"):
                if row[3] < 0:
                    row = tuple(-value for value in row)
                length = math.sqrt(sum(value * value for value in row[:3]))
                angle = 2 * math.atan2(length, row[3])
                scale = angle / length if length > 1e-8 else 2
                vectors.append(tuple(value * scale for value in row[:3]))
            return vectors

        def axis(clip, part, component):
            return [row[component] for row in rotation_vectors(clip, part)]

        def excursion(clip, part, component):
            values = axis(clip, part, component)
            return max(abs(value - values[0]) for value in values)

        def rotation_excursion(clip, part):
            vectors = rotation_vectors(clip, part)
            return max(
                math.sqrt(sum((a - b) ** 2 for a, b in zip(row, vectors[0])))
                for row in vectors
            )

        nod = excursion("Nod", "Head", 0)
        require(nod >= 0.40, "Nod: the head needs an emphatic forward/back nod")
        tilt = excursion("Tilt", "Hips", 2)
        require(
            0.10 <= tilt <= 0.22,
            "Tilt: the curious lean should stay small enough to show the belly",
        )
        require(
            max(
                rotation_excursion("Tilt", wing)
                for wing in ("LeftWing", "RightWing")
            ) >= 0.45,
            "Tilt: a wing must rise visibly alongside the face",
        )
        bow = excursion("Bow", "Torso", 0)
        require(bow >= 0.52, "Bow: the torso must make a deep forward bow")
        require(
            excursion("Bow", "Head", 0) >= 0.22,
            "Bow: the head should follow the torso into the greeting",
        )
        clip = "Tilt"
        hips = rotation_vectors(clip, "Hips")
        require(
            max(abs(row[axis]) for row in hips for axis in (0, 1)) <= 0.03,
            f"{clip}: the body must face forward so the belly stays visible",
        )
        scales = track(clip, "Hips", "scale")
        require(
            all(same_pose(scales[0], row, "scale") for row in scales),
            f"{clip}: Hips/scale changes the belly pattern's proportions",
        )
        for part in ("Torso", "Head"):
            # The face and central pattern span several joints. Preserve
            # every local transform so Hips moves their skin as one body.
            for path in ("translation", "rotation", "scale"):
                rows = track(clip, part, path)
                require(
                    all(same_pose(rows[0], row, path) for row in rows),
                    f"{clip}: {part}/{path} deforms the shared body pose",
                )
        for clip, minimum in (("Celebrate", 1.80), ("Stretch", 1.90)):
            left = axis(clip, "LeftWing", 2)
            right = axis(clip, "RightWing", 2)
            require(
                any(a <= -minimum and b >= minimum for a, b in zip(left, right)),
                f"{clip}: both wings must rise together, distinct from a one-wing wave",
            )
        torso_scales = track("Stretch", "Torso", "scale")
        hips = track("Stretch", "Hips", "translation")
        lengthening = max(row[1] for row in torso_scales) / torso_scales[0][1]
        rise = max(row[1] for row in hips) - hips[0][1]
        require(
            lengthening >= 1.065 and rise >= 0.08,
            "Stretch: the torso must lengthen and the hips rise in a full-body stretch",
        )
        return [
            "Extra gestures: visible nod "
            f"({math.degrees(nod):.1f}°), body tilt ({math.degrees(tilt):.1f}°), "
            f"bow ({math.degrees(bow):.1f}°), two-wing celebration/stretch; "
            f"stretch torso {lengthening:.3f}× and hips +{rise:.3f}; "
            "Tilt keeps hip scale and all local torso/head transforms rigid"
        ]

    def check_bow_clearance(self, tracks, subframes=0):
        """Check the deformed belly itself while the deeper bow leans forward."""
        bodies = [
            node
            for node in self.nodes
            if "mesh" in node
            and self.doc["meshes"][node["mesh"]].get("name") == "Body"
        ]
        require(len(bodies) == 1, "Bow: expected one skinned body surface")
        body = bodies[0]
        require("skin" in body, "Bow: body must retain its deformable skin")
        skin = self.doc["skins"][body["skin"]]
        binds = self.read(skin["inverseBindMatrices"])
        vertices = []
        for primitive in self.doc["meshes"][body["mesh"]]["primitives"]:
            attrs = primitive["attributes"]
            vertices.extend(
                (
                    position,
                    tuple(
                        (slot, weight)
                        for slot, weight in zip(slots, weights)
                        if weight > 0
                    ),
                )
                for position, slots, weights in zip(
                    self.read(attrs["POSITION"]),
                    self.read(attrs["JOINTS_0"]),
                    self.read(attrs["WEIGHTS_0"]),
                )
            )
        animation = next(a for a in self.doc["animations"] if a["name"] == "Bow")
        modes = {
            (c["target"]["node"], c["target"]["path"]): animation["samplers"][
                c["sampler"]
            ].get("interpolation", "LINEAR")
            for c in animation["channels"]
        }
        bottoms = []
        for frame, pose in sampled_poses(tracks, subframes, modes):
            worlds = self.world_matrices(pose)
            matrices = [
                multiply(worlds[joint], bind)
                for joint, bind in zip(skin["joints"], binds)
            ]
            bottom = min(
                sum(
                    weight
                    * (
                        matrices[slot][1] * x
                        + matrices[slot][5] * y
                        + matrices[slot][9] * z
                        + matrices[slot][13]
                    )
                    for slot, weight in influences
                )
                for (x, y, z), influences in vertices
            )
            require(
                bottom >= -0.0001,
                f"Bow: deformed body penetrates the floor at frame {frame:g} "
                f"({bottom:+.6f})",
            )
            bottoms.append(bottom)
        return (
            f"Bow body: {len(bottoms):,} poses, all {len(vertices):,} body vertices "
            f"sampled; minimum Y {min(bottoms):+.6f}"
        )

    def check_celebrate_hops(self, bottoms, times):
        """A genuine celebration takes off twice and lands between the flights.

        Use actual skinned soles, not the root's Y track: bending or stretching
        legs while lifting the body must not count as leaving the floor.
        """
        require(
            len(bottoms) == len(times) and len(times) >= 2,
            "Celebrate: foot samples need a matching timeline",
        )
        require(
            max(bottoms[0]) <= 0.025 and max(bottoms[-1]) <= 0.025,
            "Celebrate: both feet must be grounded at the start and finish",
        )
        require(
            min(min(row) for row in bottoms) >= -0.0001,
            "Celebrate: a sampled sole penetrates the floor",
        )
        intervals, start = [], None
        for index, row in enumerate(bottoms):
            if min(row) > 0.055:
                if start is None:
                    start = index
            elif start is not None:
                intervals.append((start, index - 1))
                start = None
        if start is not None:
            intervals.append((start, len(bottoms) - 1))
        hops = []
        for start, end in intervals:
            high = [
                index
                for index in range(start, end + 1)
                if min(bottoms[index]) >= 0.30
            ]
            if high and times[high[-1]] - times[high[0]] >= 0.08:
                hops.append((start, end))
        require(
            len(hops) >= 2,
            "Celebrate: needs at least two separate hops with both soles "
            "at least 0.30 above the floor for 0.08 seconds",
        )
        landings = []
        for (_, previous_end), (next_start, _) in zip(hops, hops[1:]):
            ground_start, longest = None, 0
            for index in range(previous_end + 1, next_start):
                if max(bottoms[index]) <= 0.025:
                    if ground_start is None:
                        ground_start = index
                    longest = max(longest, times[index] - times[ground_start])
                else:
                    ground_start = None
            require(
                longest >= 0.04,
                "Celebrate: separate hops need a landing with both feet "
                "grounded for at least 0.04 seconds",
            )
            landings.append(longest)
        peaks = [
            max(min(row) for row in bottoms[start : end + 1])
            for start, end in hops
        ]
        return (
            f"Celebrate hops: {len(hops)} distinct flights, both-sole peaks "
            + ", ".join(f"{peak:.3f}" for peak in peaks)
            + "; intervening grounded landings "
            + ", ".join(f"{duration:.3f}s" for duration in landings)
        )

    def check_sitting_contacts(self, tracks, subframes=0):
        """A seated belly carries weight while intact legs reach forward."""
        surfaces = []
        for node in self.nodes:
            if "mesh" not in node:
                continue
            mesh = self.doc["meshes"][node["mesh"]]
            name = mesh.get("name", "")
            if name != "Body" and "flexible leg" not in name:
                continue
            require("skin" in node, f"Sit: {name} needs a continuous skin")
            skin = self.doc["skins"][node["skin"]]
            binds = self.read(skin["inverseBindMatrices"])
            vertices = []
            for primitive in mesh["primitives"]:
                attrs = primitive["attributes"]
                positions = self.read(attrs["POSITION"])
                indices = self.read(attrs["JOINTS_0"])
                weights = self.read(attrs["WEIGHTS_0"])
                vertices.extend(
                    (
                        position,
                        tuple(
                            (slot, weight)
                            for slot, weight in zip(slots, row)
                            if weight > 0
                        ),
                    )
                    for position, slots, row in zip(positions, indices, weights)
                )
            surfaces.append((name, skin, binds, vertices))
        require(len(surfaces) == 3, "Sit: expected a belly and two flexible legs")
        animation = next(a for a in self.doc["animations"] if a["name"] == "Sit")
        timeline = [row[0] for row in self.read(animation["samplers"][0]["input"])]
        loop_frame = next(
            i for i, time in enumerate(timeline) if abs(time - 2.4) <= 1e-5
        )
        modes = {
            (c["target"]["node"], c["target"]["path"]): animation["samplers"][
                c["sampler"]
            ].get("interpolation", "LINEAR")
            for c in animation["channels"]
        }
        named_nodes = {node.get("name"): i for i, node in enumerate(self.nodes)}
        ankle_nodes = [named_nodes[side + "Ankle"] for side in ("Left", "Right")]
        rest_worlds = self.world_matrices()
        planted, held, bottoms = 0, 0, []
        for frame, pose in sampled_poses(tracks, subframes, modes):
            worlds = self.world_matrices(pose)
            heights = {}
            for name, skin, binds, vertices in surfaces:
                matrices = [
                    multiply(worlds[joint], bind)
                    for joint, bind in zip(skin["joints"], binds)
                ]
                heights[name] = min(
                    sum(
                        weight
                        * (
                            matrices[slot][1] * x
                            + matrices[slot][5] * y
                            + matrices[slot][9] * z
                            + matrices[slot][13]
                        )
                        for slot, weight in influences
                    )
                    for (x, y, z), influences in vertices
                )
                require(
                    heights[name] > -0.002,
                    f"Sit: {name} penetrates the floor at frame {frame:g}",
                )
            bottoms.append(heights["Body"])
            if frame >= loop_frame:
                held += 1
                require(
                    heights["Body"] < 0.012,
                    f"Sit: belly must remain seated after 2.4 seconds at frame {frame:g}",
                )
            if heights["Body"] < 0.012:
                planted += 1
                require(
                    all(
                        worlds[ankle][14] > rest_worlds[ankle][14] + 0.50
                        for ankle in ankle_nodes
                    ),
                    f"Sit: both feet must extend in front of the seated belly at frame {frame:g}",
                )
        require(
            planted >= len(bottoms) * 0.35,
            "Sit: the belly must rest on the floor for a sustained seated hold",
        )
        return (
            f"Sit seat: {len(bottoms):,} poses, belly min Y {min(bottoms):+.6f}, "
            f"{planted} seated poses with both feet extended; "
            f"all {held} hold poses stay seated; belly and legs clear the floor"
        )

    def check_foot_contacts(self, clips, subframes=0):
        feet = []
        for index, node in enumerate(self.nodes):
            if "mesh" not in node:
                continue
            mesh = self.doc["meshes"][node["mesh"]]
            if "rounded foot" in mesh.get("name", "").lower():
                require(
                    "skin" in node,
                    "Foot geometry must deform across ankle, forefoot and toe joints",
                )
                skin = self.doc["skins"][node["skin"]]
                binds = self.read(skin["inverseBindMatrices"])
                vertices = []
                for primitive in mesh["primitives"]:
                    attrs = primitive["attributes"]
                    positions = self.read(attrs["POSITION"])
                    indices = self.read(attrs["JOINTS_0"])
                    weights = self.read(attrs["WEIGHTS_0"])
                    vertices.extend(
                        (
                            position,
                            tuple(
                                (slot, weight)
                                for slot, weight in zip(slots, row)
                                if weight > 0
                            ),
                        )
                        for position, slots, row in zip(positions, indices, weights)
                    )
                low = min(position[2] for position, _ in vertices)
                high = max(position[2] for position, _ in vertices)
                vertices = [
                    (
                        position,
                        weights,
                        position[2] < low + 0.35 * (high - low),
                        position[2] > low + 0.65 * (high - low),
                    )
                    for position, weights in vertices
                ]
                used = {slot for _, weights, _, _ in vertices for slot, _ in weights}
                names = {self.nodes[skin["joints"][slot]]["name"] for slot in used}
                side = "Left" if "Left" in mesh["name"] else "Right"
                require(
                    {side + "Ankle", side + "Forefoot", side + "Toe"} <= names,
                    f"{side} foot must have ankle, ball and toe influences",
                )
                feet.append((side, skin, binds, vertices))
        require(len(feet) == 2, "Expected two rounded feet for ground-contact checks")
        modes = {
            animation["name"]: {
                (channel["target"]["node"], channel["target"]["path"]): animation[
                    "samplers"
                ][channel["sampler"]].get("interpolation", "LINEAR")
                for channel in animation["channels"]
            }
            for animation in self.doc["animations"]
        }
        summaries = []
        for name, tracks in clips.items():
            bottoms, rolls, sample_times = [], [], []
            animation = next(a for a in self.doc["animations"] if a["name"] == name)
            timeline = [
                row[0] for row in self.read(animation["samplers"][0]["input"])
            ]
            # Inspect every delivered sole vertex, including optional samples
            # between keys. This samples interpolation, rather than proving
            # all continuous times or arbitrary crossfades between clips.
            for frame, pose in sampled_poses(tracks, subframes, modes[name]):
                worlds = self.world_matrices(pose)
                heights, regions = [], []
                for _, skin, binds, vertices in feet:
                    matrices = [
                        multiply(worlds[joint], bind)
                        for joint, bind in zip(skin["joints"], binds)
                    ]
                    bottom, heel, toe = math.inf, math.inf, math.inf
                    for (x, y, z), influences, is_heel, is_toe in vertices:
                        height = sum(
                            weight
                            * (
                                matrices[slot][1] * x
                                + matrices[slot][5] * y
                                + matrices[slot][9] * z
                                + matrices[slot][13]
                            )
                            for slot, weight in influences
                        )
                        bottom = min(bottom, height)
                        if is_heel:
                            heel = min(heel, height)
                        if is_toe:
                            toe = min(toe, height)
                    heights.append(bottom)
                    regions.append((heel, toe))
                floor_tolerance = 0.0001 if name in EXTRA_GESTURES else 0.015
                require(
                    min(heights) >= -floor_tolerance,
                    f"{name}: a foot penetrates the floor at frame {frame:g} ({min(heights):.4f})",
                )
                if name not in ("Jump", "Run", "Celebrate"):
                    require(
                        min(heights) < 0.025,
                        f"{name}: neither foot supports the body at frame {frame:g}",
                    )
                if name in EXTRA_GESTURES - {"Celebrate"}:
                    require(
                        max(heights) < 0.025,
                        f"{name}: the standing gesture lifts a supporting foot "
                        f"at frame {frame:g} ({max(heights):.4f})",
                    )
                bottoms.append(heights)
                rolls.append(regions)
                key = int(frame)
                fraction = frame - key
                sample_times.append(
                    timeline[key]
                    + fraction
                    * (timeline[min(key + 1, len(timeline) - 1)] - timeline[key])
                )
            if name in ("Walk", "Run"):
                require(
                    all(max(row[foot] for row in bottoms) > 0.055 for foot in range(2)),
                    f"{name}: each foot must lift clear of the floor during its swing",
                )
                for foot in range(2):
                    support = [
                        roll[foot]
                        for bottom, roll in zip(bottoms, rolls)
                        if bottom[foot] < 0.025
                    ]
                    require(
                        any(toe > heel + 0.025 for heel, toe in support),
                        f"{name}: foot {foot} needs a heel-first contact with its toes lifted",
                    )
                    require(
                        any(heel > toe + 0.025 for heel, toe in support),
                        f"{name}: foot {foot} needs a toe push-off with its heel lifted",
                    )
            if name == "Run":
                require(
                    any(min(row) > 0.055 for row in bottoms),
                    "Run: gait needs an airborne phase with both feet clear",
                )
                require(
                    all(min(row[foot] for row in bottoms) < 0.025 for foot in range(2)),
                    "Run: each foot must have a supporting phase on the floor",
                )
            if name == "Jump":
                require(
                    any(min(row) > 0.15 for row in bottoms),
                    "Jump: both feet never leave the floor together",
                )
            if name == "Celebrate":
                summaries.append(self.check_celebrate_hops(bottoms, sample_times))
            summaries.append(
                f"{name} feet: {len(bottoms):,} poses, min Y {min(min(row) for row in bottoms):+.6f}, "
                f"lowest-foot max {max(min(row) for row in bottoms):+.6f}, "
                f"both airborne {sum(min(row) > 0.055 for row in bottoms)}/{len(bottoms)}"
            )
        return summaries

    def check_expressions(self):
        names = (
            "FaceNormal",
            "FaceSmile",
            "FaceSpiral",
            "FaceStrain",
        )
        named = {}
        parents = {}
        for index, node in enumerate(self.nodes):
            name = node.get("name")
            if name in (*names, "Head", "LeftEye", "RightEye"):
                require(name not in named, f"Duplicate expression node {name}")
                named[name] = index
            for child in node.get("children", []):
                parents[child] = index

        def descendants(index):
            result = set()
            pending = list(self.nodes[index].get("children", []))
            while pending:
                child = pending.pop()
                require(child not in result, "Expression hierarchy contains a cycle")
                result.add(child)
                pending.extend(self.nodes[child].get("children", []))
            return result

        require("Head" in named, "Expressions need a Head joint")
        groups = {}
        for name in names:
            require(name in named, f"Missing expression group {name}")
            index = named[name]
            require(
                parents.get(index) == named["Head"],
                f"{name}: expression group must follow the Head joint",
            )
            scale = self.nodes[index].get("scale", (1, 1, 1))
            if name == "FaceNormal":
                require(close(scale, (1, 1, 1)), "Default expression must be visible")
            else:
                require(
                    all(0 < value <= 0.0011 for value in scale),
                    f"{name}: alternative must start hidden with positive scale",
                )
            group = descendants(index)
            require(
                any("mesh" in self.nodes[child] for child in group),
                f"{name}: expression contains no visible geometry",
            )
            groups[name] = group
        for eye in ("LeftEye", "RightEye"):
            require(
                eye in named and named[eye] in groups["FaceNormal"],
                f"{eye}: blinking eye must be inside the normal expression group",
            )
        expression_nodes = {named[name] for name in names}
        require(
            all(
                channel["target"]["node"] not in expression_nodes
                for animation in self.doc.get("animations", [])
                for channel in animation["channels"]
            ),
            "Motion clips must not overwrite the user's chosen expression",
        )
        return (
            "Normal, smiling, spiral and strained eyes follow the head "
            "independently of motion"
        )

    def check_walk_baseline(self, baseline):
        def walk_tracks(model):
            animation = next(
                (
                    clip
                    for clip in model.doc.get("animations", [])
                    if clip.get("name") == "Walk"
                ),
                None,
            )
            require(animation is not None, "Walk regression: model has no Walk clip")
            tracks = {}
            for channel in animation["channels"]:
                target = channel["target"]
                node = model.nodes[target["node"]]
                key = (node.get("name"), target["path"])
                require(
                    key not in tracks, f"Walk regression: ambiguous node name {key}"
                )
                sampler = animation["samplers"][channel["sampler"]]
                tracks[key] = (
                    sampler.get("interpolation", "LINEAR"),
                    model.read(sampler["input"]),
                    model.read(sampler["output"]),
                )
            return tracks

        previous, current = walk_tracks(baseline), walk_tracks(self)
        for key, (interpolation, times, rows) in previous.items():
            require(key in current, f"Walk regression: removed existing channel {key}")
            actual_interpolation, actual_times, actual_rows = current[key]
            require(
                interpolation == actual_interpolation
                and len(times) == len(actual_times)
                and all(close(a, b) for a, b in zip(times, actual_times)),
                f"Walk regression: changed timing or interpolation for {key}",
            )
            # The requested heel/toe pass changes leg IK, but the timing and
            # established upper-body cadence must remain untouched.
            if key[0] not in {
                side + part
                for side in ("Left", "Right")
                for part in ("Leg", "Knee", "Ankle")
            }:
                require(
                    len(rows) == len(actual_rows)
                    and all(same_pose(a, b, key[1]) for a, b in zip(rows, actual_rows)),
                    f"Walk regression: changed established upper-body pose for {key}",
                )
        defaults = {
            "translation": (0, 0, 0),
            "rotation": (0, 0, 0, 1),
            "scale": (1, 1, 1),
        }
        nodes = {node.get("name"): node for node in self.nodes}
        for name, path in current.keys() - previous.keys():
            if name in {
                side + part
                for side in ("Left", "Right")
                for part in ("Forefoot", "Toe")
            }:
                continue
            neutral = nodes[name].get(path, defaults[path])
            require(
                all(same_pose(row, neutral, path) for row in current[(name, path)][2]),
                f"Walk regression: added channel {(name, path)} must stay at rest",
            )
        return "Walk retains its timing and established upper-body poses; leg and toe articulation may change"

    def check_established_clips(self, baseline):
        """Adding gestures must not change any key of the original eight clips."""

        def tracks(model, clip_name):
            animation = next(
                (
                    clip
                    for clip in model.doc.get("animations", [])
                    if clip.get("name") == clip_name
                ),
                None,
            )
            require(animation is not None, f"Regression: missing {clip_name} clip")
            result = {}
            for channel in animation["channels"]:
                target = channel["target"]
                name = model.nodes[target["node"]].get("name")
                key = (name, target["path"])
                require(key not in result, f"{clip_name}: ambiguous track {key}")
                sampler = animation["samplers"][channel["sampler"]]
                result[key] = (
                    sampler.get("interpolation", "LINEAR"),
                    model.read(sampler["input"]),
                    model.read(sampler["output"]),
                )
            return result

        count = 0
        for name in sorted(ESTABLISHED_CLIPS):
            previous, current = tracks(baseline, name), tracks(self, name)
            require(
                previous.keys() == current.keys(),
                f"{name} regression: established animated properties changed",
            )
            for key, (interpolation, times, rows) in previous.items():
                actual_interpolation, actual_times, actual_rows = current[key]
                require(
                    interpolation == actual_interpolation
                    and len(times) == len(actual_times)
                    and all(close(a, b) for a, b in zip(times, actual_times)),
                    f"{name} regression: timing/interpolation changed for {key}",
                )
                require(
                    len(rows) == len(actual_rows)
                    and all(same_pose(a, b, key[1]) for a, b in zip(rows, actual_rows)),
                    f"{name} regression: an established pose changed for {key}",
                )
                count += len(rows)
        return (
            f"Regression: all {len(ESTABLISHED_CLIPS)} established clips retain "
            f"their complete timing, interpolation and {count:,} property keys"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "model",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets/models/dashmaru.glb",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Previous GLB whose Walk timing and upper-body poses must remain unchanged",
    )
    parser.add_argument(
        "--preserve-existing",
        type=Path,
        help="Previous GLB whose original eight clips must remain fully unchanged",
    )
    parser.add_argument(
        "--subframes",
        type=int,
        default=0,
        metavar="N",
        help="Extra foot-contact samples per key interval (0: keys only; 3: quarter steps)",
    )
    args = parser.parse_args()
    if args.subframes < 0:
        parser.error("--subframes must be zero or a positive integer")
    try:
        model = Model(args.model)
        mesh_count, triangle_count = model.check_meshes()
        surface_summary = check_surface_quality(model, require)
        bib_summary = model.check_bib_clearance()
        skin_summary = model.check_skins()
        summaries = model.check_animations(args.subframes)
        expression_summary = model.check_expressions()
        walk_summary = (
            model.check_walk_baseline(Model(args.baseline)) if args.baseline else None
        )
        established_summary = (
            model.check_established_clips(Model(args.preserve_existing))
            if args.preserve_existing
            else None
        )
    except (
        InvalidModel,
        OSError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        struct.error,
    ) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(
        f"PASS: {args.model.name} — {mesh_count} meshes, {triangle_count:,} triangles, "
        f"{len(model.accessors)} bounded finite accessors"
    )
    for summary in summaries:
        print(f"  {summary}")
    print(f"  {skin_summary}")
    print(f"  {expression_summary}")
    print(f"  {bib_summary}")
    print(f"  {surface_summary}")
    if walk_summary:
        print(f"  {walk_summary}")
    if established_summary:
        print(f"  {established_summary}")
    print("  Every loop joins matching poses and keys all shared properties.")
    print("  Gestures return to neutral except Sit, which stays seated from 2.4s.")
    print("  All scales stay positive.")
    print(
        "  Sampled soles respect the floor tolerance; locomotion rolls "
        "from heel contact to toe push-off."
    )
    print("  Nod, Tilt, Bow and Stretch keep both feet in ground contact.")
    print("  Tilt faces forward and preserves the central pattern.")
    print("  Celebrate makes two or more clear hops and lands between them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

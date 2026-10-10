"""Check face markings and rounded surfaces in the delivered GLB.

Checks use exported triangles and normals rather than importing the generator.
Run this directly, or call check_surface_quality from the main model checker.
"""

from collections import Counter
import math


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _mean(rows):
    return tuple(sum(row[axis] for row in rows) / len(rows) for axis in range(3))


def _mesh(model, mesh):
    primitive = mesh["primitives"][0]
    vertices = model.read(primitive["attributes"]["POSITION"])
    normals = model.read(primitive["attributes"]["NORMAL"])
    indices = [row[0] for row in model.read(primitive["indices"])]
    faces = [tuple(indices[i : i + 3]) for i in range(0, len(indices), 3)]
    return vertices, normals, faces


def _face_normal(vertices, face):
    a, b, c = (vertices[index] for index in face)
    return _cross(_sub(b, a), _sub(c, a))


def _topology(name, faces, boundary_count, require):
    edges = Counter()
    directed = Counter()
    for a, b, c in faces:
        for start, end in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted((start, end)))] += 1
            directed[start, end] += 1
    require(
        all(count <= 2 for count in edges.values()),
        f"{name}: non-manifold edge",
    )
    require(
        sum(count == 1 for count in edges.values()) == boundary_count,
        f"{name}: unexpected open boundary",
    )
    for (a, b), count in edges.items():
        if count == 2:
            require(
                directed[a, b] == directed[b, a] == 1,
                f"{name}: adjacent triangles disagree on their outward side",
            )


def _check_convex_closed(name, vertices, normals, faces, require):
    _topology(name, faces, 0, require)
    center = _mean(vertices)
    volume = 0.0
    for face in faces:
        triangle = [vertices[index] for index in face]
        geometric = _face_normal(vertices, face)
        outward = _sub(_mean(triangle), center)
        require(
            _dot(geometric, outward) > 0,
            f"{name}: inverted or collapsed surface triangle",
        )
        require(
            _dot(geometric, _mean([normals[index] for index in face])) > 0,
            f"{name}: normals disagree with its surface",
        )
        a, b, c = [_sub(vertex, center) for vertex in triangle]
        volume += _dot(a, _cross(b, c)) / 6
    require(volume > 0, f"{name}: no positive enclosed volume")


def check_surface_quality(model, require):
    meshes = {mesh["name"]: mesh for mesh in model.doc["meshes"]}
    patches = [
        name
        for name in meshes
        if name in ("Joined blue face mask", "White bib", "Red roundel")
        or name.endswith(("eye ink", "eye white", "pupil"))
    ]
    require(len(patches) == 17, "Expected all 17 curved face and body markings")
    for name in patches:
        vertices, normals, faces = _mesh(model, meshes[name])
        for face in faces:
            require(
                _face_normal(vertices, face)[2] > 0,
                f"{name}: reversed marking triangle (center fan or ring winding)",
            )
        require(
            all(normal[2] > 0 for normal in normals),
            f"{name}: inward shading normal creates a spot in the marking",
        )

    # Inspect every alternate face at full scale, as Flutter Scene displays it.
    overrides = {
        (index, "scale"): (1, 1, 1)
        for index, node in enumerate(model.nodes)
        if node.get("name", "").startswith("Face")
    }
    worlds = model.world_matrices(overrides)
    mesh_nodes = {
        node["mesh"]: index for index, node in enumerate(model.nodes) if "mesh" in node
    }
    for mesh_index, mesh in enumerate(model.doc["meshes"]):
        name = mesh["name"]
        if not name.endswith("eye ink"):
            continue
        vertices, _, _ = _mesh(model, mesh)
        matrix = worlds[mesh_nodes[mesh_index]]
        xs = [
            matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12]
            for x, y, z in vertices
        ]
        require(
            max(xs) <= 1e-7 if "Left" in name else min(xs) >= -1e-7,
            f"{name}: coplanar eye outlines overlap at the bridge of the nose",
        )

    strokes = [
        name
        for name in meshes
        if name.endswith(("expression stroke", "squeezed eyelid"))
    ]
    require(len(strokes) == 6, "Expected both eyes of all three alternate faces")
    minimum_facing = 1.0
    for name in strokes:
        vertices, normals, faces = _mesh(model, meshes[name])
        sides = 20
        require(len(vertices) % sides == 0, f"{name}: incomplete swept ring")
        centers = [
            _mean(vertices[i : i + sides]) for i in range(0, len(vertices), sides)
        ]
        _topology(name, faces, sides * 2, require)
        for face in faces:
            radial = _mean(
                [_sub(vertices[index], centers[index // sides]) for index in face]
            )
            geometric = _face_normal(vertices, face)
            denominator = math.sqrt(_dot(radial, radial) * _dot(geometric, geometric))
            facing = _dot(geometric, radial) / max(denominator, 1e-30)
            minimum_facing = min(minimum_facing, facing)
            require(
                facing > 0.05,
                f"{name}: tube folds inside out at a bend (facing {facing:.6f})",
            )
            require(
                _dot(geometric, _mean([normals[index] for index in face])) > 0,
                f"{name}: stroke normals disagree with its surface",
            )

    caps = [name for name in meshes if " stroke cap " in name]
    require(len(caps) == 12, "Every alternate eye stroke needs two rounded caps")
    for name in caps:
        _check_convex_closed(name, *_mesh(model, meshes[name]), require)

    beak = "Pointed brown beak"
    require(beak in meshes, "Missing rounded beak")
    vertices, normals, faces = _mesh(model, meshes[beak])
    _check_convex_closed(beak, vertices, normals, faces, require)
    center_x = (min(v[0] for v in vertices) + max(v[0] for v in vertices)) / 2
    center_y = (min(v[1] for v in vertices) + max(v[1] for v in vertices)) / 2
    tip_z = max(v[2] for v in vertices)
    section_z = tip_z - 0.010
    section = []
    for face in faces:
        for a, b in zip(face, (face[1], face[2], face[0])):
            start, end = vertices[a], vertices[b]
            if (start[2] < section_z) != (end[2] < section_z):
                fraction = (section_z - start[2]) / (end[2] - start[2])
                x, y = (
                    start[axis] + fraction * (end[axis] - start[axis])
                    for axis in (0, 1)
                )
                section.append(math.hypot(x - center_x, y - center_y))
    require(section, "Beak has no rounded tip cross-section")
    tip_radius = min(section)
    require(tip_radius >= 0.008, "Beak tip has regressed to a pin-sharp cone")
    return (
        f"Surface quality: {len(patches)} outward markings, "
        f"no eye-outline overlap, {len(strokes)} unflipped eye strokes "
        f"(minimum facing {minimum_facing:.4f}), {len(caps)} closed caps; "
        f"beak closed and rounded (tip section radius {tip_radius:.5f})"
    )


def main():
    import argparse
    from pathlib import Path
    import sys

    from check_dashmaru import InvalidModel, Model, require

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "model",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets/models/dashmaru.glb",
    )
    args = parser.parse_args()
    try:
        print("PASS:", check_surface_quality(Model(args.model), require))
    except (InvalidModel, OSError, ValueError, KeyError, IndexError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

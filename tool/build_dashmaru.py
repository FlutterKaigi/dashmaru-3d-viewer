#!/usr/bin/env python3
"""Rebuild the hand-authored Dashmaru GLB, using only Python's standard library.

Y is up, +Z is the face, metres are arbitrary (height 3.04).
The model uses parametric geometry with no embedded images.
Every marking follows the curved body surface.
Run: python3 tool/build_dashmaru.py
"""

import json
import math
import struct
from pathlib import Path

from dashmaru_expressions import build_expressions, eye_ink_contour
from dashmaru_materials import polish_materials

PI = math.pi
sin, cos, sqrt = math.sin, math.cos, math.sqrt
OUT = Path(__file__).resolve().parents[1] / "assets" / "models"
MODEL_RIGHTS = {
    "license": "CC-BY-NC-ND-4.0",
    "licenseUrl": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
    "licenseScope": "FlutterKaigi's original contributions only; underlying Dash rights and permissions are not changed.",
    "noticeUrl": "https://github.com/FlutterKaigi/dashmaru-3d-viewer/blob/main/assets/models/NOTICE.md",
    "underlyingCharacter": {
        "name": "Dash",
        "informationUrl": "https://docs.flutter.dev/dash",
    },
}


def vadd(a, b):
    return tuple(x + y for x, y in zip(a, b))


def vsub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def unit(v):
    length = sqrt(sum(x * x for x in v))
    return tuple(x / max(length, 1e-12) for x in v)


def normals(vertices, faces):
    result = [[0.0, 0.0, 0.0] for _ in vertices]
    for a, b, c in faces:
        n = cross(vsub(vertices[b], vertices[a]), vsub(vertices[c], vertices[a]))
        for i in (a, b, c):
            for j in range(3):
                result[i][j] += n[j]
    return [unit(n) for n in result]


class Glb:
    def __init__(self):
        self.data = bytearray()
        self.doc = {
            "asset": {
                "version": "2.0",
                "generator": "Dashmaru parametric sculpture / Python",
                "copyright": "Original contributions to Dashmaru character design, 3D model and animations (c) 2026 FlutterKaigi. CC BY-NC-ND 4.0. Rights in the underlying Dash character remain with their respective holders.",
                "extras": {
                    **MODEL_RIGHTS,
                    "source": "https://github.com/FlutterKaigi/dashmaru-3d-viewer",
                },
            },
            "scene": 0,
            "scenes": [{"name": "Dashmaru", "nodes": [0]}],
            "nodes": [],
            "meshes": [],
            "materials": [],
            "animations": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": [],
        }
        self.node("Dashmaru")

    def accessor(self, values, kind, component=5126, target=None):
        while len(self.data) % 4:
            self.data.append(0)
        start = len(self.data)
        scalar = kind == "SCALAR"
        rows = [(x,) for x in values] if scalar else values
        flat = [v for row in rows for v in row]
        self.data.extend(
            struct.pack(
                "<" + {5126: "f", 5125: "I", 5123: "H"}[component] * len(flat), *flat
            )
        )
        view = {"buffer": 0, "byteOffset": start, "byteLength": len(self.data) - start}
        if target:
            view["target"] = target
        self.doc["bufferViews"].append(view)
        acc = {
            "bufferView": len(self.doc["bufferViews"]) - 1,
            "componentType": component,
            "count": len(values),
            "type": kind,
            "min": [min(row[j] for row in rows) for j in range(len(rows[0]))],
            "max": [max(row[j] for row in rows) for j in range(len(rows[0]))],
        }
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

    def material(self, name, rgb, roughness=0.85):
        # glTF factors are linear, whereas the reference palette is sRGB.
        color = [
            ((c / 255 + 0.055) / 1.055) ** 2.4 if c > 10 else c / 255 / 12.92
            for c in rgb
        ]
        self.doc["materials"].append(
            {
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": color + [1],
                    "metallicFactor": 0,
                    "roughnessFactor": roughness,
                },
                "doubleSided": True,
            }
        )
        return len(self.doc["materials"]) - 1

    def node(self, name, parent=None, translation=None, mesh=None):
        node = {"name": name}
        if translation is not None:
            node["translation"] = list(translation)
        if mesh is not None:
            node["mesh"] = mesh
        idx = len(self.doc["nodes"])
        self.doc["nodes"].append(node)
        if parent is not None:
            self.doc["nodes"][parent].setdefault("children", []).append(idx)
        return idx

    def mesh(
        self, name, vertices, faces, material, parent=0, translation=None, weights=None
    ):
        # Weld the two sides of feathers, poles and tube seams before averaging
        # normals. Extra tessellation alone cannot fix split shading at a seam.
        unique, remap, lookup = [], [], {}
        for vertex in vertices:
            key = tuple(round(value, 8) for value in vertex)
            if key not in lookup:
                lookup[key] = len(unique)
                unique.append(vertex)
            remap.append(lookup[key])
        faces = [tuple(remap[i] for i in face) for face in faces]
        faces = [face for face in faces if len(set(face)) == 3]
        vertices = unique
        if parent == 0:
            weights = weights or body_weights
            vertices = [vadd(v, translation or (0, 0, 0)) for v in vertices]
            translation = None
        attrs = {
            "POSITION": self.accessor(vertices, "VEC3", target=34962),
            "NORMAL": self.accessor(normals(vertices, faces), "VEC3", target=34962),
        }
        if weights:
            influences = [[(n, w) for n, w in weights(v) if w > 0] for v in vertices]
            attrs["JOINTS_0"] = self.accessor(
                [
                    tuple(joints.index(n) for n, _ in row) + (0,) * (4 - len(row))
                    for row in influences
                ],
                "VEC4",
                5123,
                34962,
            )
            attrs["WEIGHTS_0"] = self.accessor(
                [
                    tuple(w for _, w in row) + (0,) * (4 - len(row))
                    for row in influences
                ],
                "VEC4",
                target=34962,
            )
        indices = self.accessor(
            [i for face in faces for i in face], "SCALAR", 5125, 34963
        )
        self.doc["meshes"].append(
            {
                "name": name,
                "primitives": [
                    {"attributes": attrs, "indices": indices, "material": material}
                ],
            }
        )
        node = self.node(name, parent, translation, len(self.doc["meshes"]) - 1)
        if weights:
            self.doc["nodes"][node]["skin"] = 0
            # Skin matrices already include the skeleton root transform. Keep
            # mesh nodes at scene root, as required by portable glTF skinning.
            self.doc["nodes"][parent]["children"].remove(node)
            self.doc["scenes"][0]["nodes"].append(node)
        return node

    def clip(self, name, tracks):
        samplers, channels = [], []
        for node, path, times, values in tracks:
            samplers.append(
                {
                    "input": self.accessor(times, "SCALAR"),
                    "output": self.accessor(
                        values, "VEC4" if path == "rotation" else "VEC3"
                    ),
                    "interpolation": "LINEAR",
                }
            )
            channels.append(
                {"sampler": len(samplers) - 1, "target": {"node": node, "path": path}}
            )
        self.doc["animations"].append(
            {"name": name, "samplers": samplers, "channels": channels}
        )

    def save(self):
        self.doc["buffers"] = [{"byteLength": len(self.data)}]
        encoded = json.dumps(self.doc, separators=(",", ":")).encode()
        encoded += b" " * (-len(encoded) % 4)
        self.data += b"\x00" * (-len(self.data) % 4)
        body = (
            struct.pack("<I4s", len(encoded), b"JSON")
            + encoded
            + struct.pack("<I4s", len(self.data), b"BIN\x00")
            + self.data
        )
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "dashmaru.glb").write_bytes(
            struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body
        )
        summary = {
            **MODEL_RIGHTS,
            "height": 3.04,
            "front": "+Z",
            "up": "+Y",
            "meshes": len(self.doc["meshes"]),
            "joints": len(joints),
            "rig": "Soft body and crest, distributed wing flex, two-bone IK legs and articulated forefeet",
            "triangles": sum(
                self.doc["accessors"][m["primitives"][0]["indices"]]["count"] // 3
                for m in self.doc["meshes"]
            ),
            "animations": [
                {"name": a["name"], "tracks": len(a["channels"])}
                for a in self.doc["animations"]
            ],
            "bytes": 12 + len(body),
        }
        (OUT / "dashmaru_manifest.json").write_text(
            json.dumps(summary, indent=2) + "\n"
        )
        print(json.dumps(summary, indent=2))


g = Glb()
MINT = g.material("Body | pale cyan #C8FCFE", (200, 252, 254))
BLUE = g.material("Feathers and Fuji | sky blue #68D8FB", (104, 216, 251))
INK = g.material("Embroidered outlines | black", (0, 0, 0))
WHITE = g.material("Snow, eyes and bib | white", (255, 255, 255))
RED = g.material("Japan badge | raspberry #E83568", (232, 53, 104))
BROWN = g.material("Beak and feet | warm brown #634936", (99, 73, 54))


def smooth(a, b, t):
    t = max(0, min(1, (t - a) / (b - a)))
    return t * t * (3 - 2 * t)


joints, bind_positions = [], {}


def bone(name, position, parent=0):
    node = g.node(name, parent, vsub(position, bind_positions.get(parent, (0, 0, 0))))
    joints.append(node)
    bind_positions[node] = position
    return node


hips = bone("Hips", (0, 0.68, 0))
torso = bone("Torso", (0, 1.20, 0), hips)
head = bone("Head", (0, 1.75, 0), torso)
crest = bone("Crest", (0, 2.50, 0), head)
crest_tip = bone("CrestTip", (0, 2.87, 0), crest)
wing_nodes, wing_bends, wing_tips, legs, knees, ankles = [], [], [], [], [], []
wing_soft = []
forefeet, toes = [], []
for side, sign in [("Left", -1), ("Right", 1)]:
    shoulder = bone(side + "Wing", (sign * 0.84, 2.00, 0), head)
    bend = bone(side + "WingBend", (sign * 1.00, 1.65, 0), shoulder)
    tip = bone(side + "WingTip", (sign * 1.03, 1.28, 0), bend)
    wing_soft.append(
        [
            bone(side + "WingSoftUpper", (sign * 0.96, 1.83, 0), shoulder),
            bone(side + "WingSoftMiddle", (sign * 1.02, 1.47, 0), bend),
            bone(side + "WingSoftTip", (sign * 1.04, 1.10, 0), tip),
        ]
    )
    wing_nodes.append(shoulder)
    wing_bends.append(bend)
    wing_tips.append(tip)
    leg = bone(side + "Leg", (sign * 0.29, 0.64, 0.02))
    knee = bone(side + "Knee", (sign * 0.29, 0.405, 0.02), leg)
    ankle = bone(side + "Ankle", (sign * 0.29, 0.17, 0.02), knee)
    legs.append(leg)
    knees.append(knee)
    ankles.append(ankle)
    forefoot = bone(side + "Forefoot", (sign * 0.3248, 0.105, 0.25), ankle)
    forefeet.append(forefoot)
    toes.append(bone(side + "Toe", (sign * 0.3248, 0.10, 0.385), forefoot))
tail = bone("Tail", (0, 0.94, -0.78), hips)

# All authored vertices use model-space bind coordinates. Eye parts are rigid
# children of Head so their tiny blink scales do not distort neighbouring skin.
inverse_binds = []
for node in joints:
    x, y, z = bind_positions[node]
    inverse_binds.append((1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -x, -y, -z, 1))
g.doc["skins"] = [
    {
        "name": "Dashmaru soft character rig",
        "skeleton": 0,
        "joints": joints,
        "inverseBindMatrices": g.accessor(inverse_binds, "MAT4"),
    }
]


def body_weights(v):
    y = v[1]
    if y > 2.48:
        base = smooth(2.48, 2.72, y)
        tip = smooth(2.72, 3.04, y)
        return [(head, 1 - base), (crest, base * (1 - tip)), (crest_tip, base * tip)]
    upper = smooth(1.06, 1.47, y)
    lower = smooth(0.69, 1.10, y)
    return [
        (hips, (1 - upper) * (1 - lower)),
        (torso, (1 - upper) * lower),
        (head, upper),
    ]


def ellipsoid(
    name, center, radii, material, parent=0, segments=80, rings=48, weights=None
):
    vertices = []
    for j in range(rings + 1):
        lat = PI * j / rings
        for i in range(segments):
            a = 2 * PI * i / segments
            vertices.append(
                (
                    radii[0] * sin(lat) * cos(a),
                    radii[1] * cos(lat),
                    radii[2] * sin(lat) * sin(a),
                )
            )
    faces = []
    for j in range(rings):
        for i in range(segments):
            a = j * segments + i
            b = j * segments + (i + 1) % segments
            faces.extend([(a, b, a + segments), (b, b + segments, a + segments)])
    return g.mesh(name, vertices, faces, material, parent, center, weights)


BODY_Y = 1.58
RX, RY, RZ = 1.0, 1.02, 0.95
ellipsoid("Body", (0, BODY_Y, 0), (RX, RY, RZ), MINT, segments=128, rings=80)


def surface(x, y, offset=0):
    radial = (x / RX) ** 2 + ((y - BODY_Y) / RY) ** 2
    if radial > 0.996:
        scale = sqrt(0.996 / radial)
        x *= scale
        y = BODY_Y + (y - BODY_Y) * scale
    q = max(0.004, 1 - (x / RX) ** 2 - ((y - BODY_Y) / RY) ** 2)
    return (x, y, RZ * sqrt(q) + offset)


def bezier(start, segments, samples=12):
    pts = []
    a = start
    for b, c, d in segments:
        for i in range(samples):
            t = i / samples
            u = 1 - t
            pts.append(
                tuple(
                    u * u * u * a[j]
                    + 3 * u * u * t * b[j]
                    + 3 * u * t * t * c[j]
                    + t * t * t * d[j]
                    for j in range(2)
                )
            )
        a = d
    return pts


def circle(cx, cy, rx, ry=None, n=96):
    if ry is None:
        ry = rx
    return [
        (cx + rx * cos(2 * PI * i / n), cy + ry * sin(2 * PI * i / n)) for i in range(n)
    ]


def patch(
    name,
    contour,
    material,
    offset=0.005,
    parent=0,
    origin=(0, 0, 0),
    center=None,
    rings=14,
    conform_edge=False,
):
    # Radial tessellation maps the marking onto the ellipsoid, not a flat decal.
    if center is None:
        center = tuple(sum(p[j] for p in contour) / len(contour) for j in range(2))
    if conform_edge:
        # Clamp the boundary once before interpolating inward. Otherwise paths
        # beyond the body's silhouette collapse onto the same horizon and leave
        # long triangle chords cutting through the curved belly.
        contour = [surface(x, y)[:2] for x, y in contour]
    n = len(contour)
    vertices = [vsub(surface(*center, offset), origin)]
    for k in range(1, rings + 1):
        r = k / rings
        if conform_edge:
            # Concentrate rings near the silhouette, where curvature in this
            # projected parameterization is greatest. The offset stays small.
            r = 1 - (1 - r) ** 2
        for x, y in contour:
            vertices.append(
                vsub(
                    surface(
                        center[0] + r * (x - center[0]),
                        center[1] + r * (y - center[1]),
                        offset,
                    ),
                    origin,
                )
            )
    faces = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    for k in range(rings - 1):
        for i in range(n):
            a = 1 + k * n + i
            b = 1 + k * n + (i + 1) % n
            # Match the center fan before correcting the artist path's winding.
            # Opposite fan/ring winding cancels normals into a false dark spot.
            faces.extend([(a, a + n, b), (b, a + n, b + n)])
    # Ensure front-facing normals, independent of clockwise artist path.
    if (
        sum(
            cross(vsub(vertices[b], vertices[a]), vsub(vertices[c], vertices[a]))[2]
            for a, b, c in faces
        )
        < 0
    ):
        faces = [(a, c, b) for a, b, c in faces]
    return g.mesh(name, vertices, faces, material, parent)


def tube(name, points, radius, material, parent=0, closed=True, origin=(0, 0, 0)):
    n = len(points)
    sides = 20
    vertices = []
    for i, p in enumerate(points):
        tangent = unit(
            vsub(
                points[(i + 1) % n] if closed or i < n - 1 else p,
                points[(i - 1) % n] if closed or i > 0 else p,
            )
        )
        side = unit(cross(tangent, (0, 0, 1)))
        other = unit(cross(tangent, side))
        for j in range(sides):
            angle = 2 * PI * j / sides
            vertices.append(
                vsub(
                    vadd(
                        p,
                        tuple(
                            radius * (cos(angle) * side[k] + sin(angle) * other[k])
                            for k in range(3)
                        ),
                    ),
                    origin,
                )
            )
    faces = []
    for i in range(n if closed else n - 1):
        for j in range(sides):
            a = i * sides + j
            b = i * sides + (j + 1) % sides
            c = ((i + 1) % n) * sides + j
            d = ((i + 1) % n) * sides + (j + 1) % sides
            faces.extend([(a, b, c), (b, d, c)])
    return g.mesh(name, vertices, faces, material, parent)


def outlined_patch(
    name,
    contour,
    material,
    width=0.018,
    offset=0.012,
    center=None,
    *,
    rings=14,
    conform_edge=False,
):
    patch(
        name,
        contour,
        material,
        offset,
        center=center,
        rings=rings,
        conform_edge=conform_edge,
    )
    tube(
        name + " outline",
        [surface(x, y, offset + 0.002) for x, y in contour],
        width,
        INK,
    )


mask = bezier(
    (0, 2.04),
    [
        ((0.19, 2.30), (0.52, 2.28), (0.63, 2.04)),
        ((0.81, 1.67), (0.49, 1.42), (0.20, 1.47)),
        ((0.10, 1.48), (0.04, 1.52), (0, 1.52)),
        ((-0.04, 1.52), (-0.10, 1.48), (-0.20, 1.47)),
        ((-0.49, 1.42), (-0.81, 1.67), (-0.63, 2.04)),
        ((-0.52, 2.28), (-0.19, 2.30), (0, 2.04)),
    ],
    20,
)
mask = [(x * 0.96, 1.80 + (y - 1.80) * 0.96) for x, y in mask]
outlined_patch("Joined blue face mask", mask, BLUE, 0.019, center=(0, 1.80))

bib = bezier(
    (-0.32, 1.34),
    [
        ((-0.12, 1.18), (0.11, 1.18), (0.32, 1.36)),
        ((0.46, 1.22), (0.59, 1.02), (0.70, 0.80)),
        ((0.49, 0.61), (0.27, 0.574), (0, 0.565)),
        ((-0.27, 0.574), (-0.49, 0.61), (-0.70, 0.80)),
        ((-0.59, 1.02), (-0.46, 1.22), (-0.32, 1.34)),
    ],
    60,
)
outlined_patch(
    "White bib",
    bib,
    WHITE,
    0.017,
    center=(0, 0.97),
    rings=28,
    conform_edge=True,
)
outlined_patch("Red roundel", circle(0, 0.94, 0.204), RED, 0.017, 0.023)

# Each eye has its own pivot, so Blink closes only the eye, retaining the mask.
eyes = []
lids = []
normal_face = g.node("FaceNormal", head, (0, 0, 0))
for side, x in [("Left", -0.167), ("Right", 0.167)]:
    eyey = 1.81
    origin = surface(x, eyey, 0.04)
    pivot = g.node(side + "Eye", normal_face, vsub(origin, bind_positions[head]))
    eyes.append(pivot)
    patch(
        side + " eye ink",
        eye_ink_contour(x, eyey, circle),
        INK,
        0.029,
        pivot,
        origin,
        center=(x, eyey),
        rings=8,
    )
    patch(
        side + " eye white",
        circle(x, eyey, 0.134, 0.126),
        WHITE,
        0.034,
        pivot,
        origin,
        center=(x, eyey),
        rings=8,
    )
    patch(
        side + " pupil",
        circle(x, eyey, 0.036),
        INK,
        0.040,
        pivot,
        origin,
        center=(x, eyey),
        rings=5,
    )
    lid = g.node(side + "Lid", normal_face, vsub(origin, bind_positions[head]))
    lids.append(lid)
    g.doc["nodes"][lid]["scale"] = [0.001, 0.001, 0.001]
    lid_points = []
    for i in range(33):
        dx = 0.138 * (2 * i / 32 - 1)
        lid_points.append(
            surface(x + dx, eyey - 0.014 * (1 - (dx / 0.138) ** 2), 0.057)
        )
    tube(
        side + " closed eyelid",
        lid_points,
        0.012,
        INK,
        lid,
        closed=False,
        origin=origin,
    )

expression_groups = build_expressions(
    g,
    head,
    bind_positions[head],
    patch,
    tube,
    surface,
    circle,
    INK,
    WHITE,
)

# Keep the tapered brown silhouette, but ease the shoulder into a softly curved
# cone and a rounded nose. The tip has a finite cap instead of a pin-sharp point.
beak_profile = bezier(
    (0.910, 0.0),
    [
        ((0.910, 0.118), (0.935, 0.144), (0.955, 0.144)),
        ((1.050, 0.144), (1.300, 0.076), (1.440, 0.035)),
        ((1.481, 0.023), (1.492, 0.016), (1.492, 0.0)),
    ],
    36,
) + [(1.492, 0.0)]
beak_sides = 128
verts = []
faces = []
for z, r in beak_profile:
    for i in range(beak_sides):
        a = 2 * PI * i / beak_sides
        verts.append((r * cos(a), 1.568 + r * sin(a), z))
for j in range(len(beak_profile) - 1):
    for i in range(beak_sides):
        a = j * beak_sides + i
        b = j * beak_sides + (i + 1) % beak_sides
        faces.extend([(a, b, a + beak_sides), (b, b + beak_sides, a + beak_sides)])
g.mesh("Pointed brown beak", verts, faces, BROWN)

# Fuji is a truncated mountain, not a party hat: wide base, flat summit,
# and an undulating black snowline that wraps all the way around.
hatbase = 2.50
hatheight = 0.54


def mountain_radius(y):
    straight = 0.337 + (0.118 - 0.337) * (y - hatbase) / hatheight
    if 2.543 < y < 2.560:
        # A very small Hermite fillet eases the shoulder where the mountain
        # emerges from the head; the long trapezoidal sides stay straight.
        t = (y - 2.543) / 0.017
        return (
            (2 * t**3 - 3 * t**2 + 1) * 0.327
            + (t**3 - 2 * t**2 + t) * 0.017 * -2.5
            + (-2 * t**3 + 3 * t**2) * (0.337 - 0.219 * 0.060 / 0.54)
            + (t**3 - t**2) * 0.017 * (-0.219 / 0.54)
        )
    if y <= 2.543:
        return 0.337 + (0.327 - 0.337) * (y - hatbase) / 0.043
    return straight


verts = []
faces = []
mountain_heights = (
    [hatbase + 0.043 * j / 8 for j in range(8)]
    + [2.543 + 0.017 * j / 12 for j in range(12)]
    + [2.560 + 0.400 * j / 24 for j in range(25)]
)
for y in mountain_heights:
    r = mountain_radius(y)
    for i in range(96):
        a = 2 * PI * i / 96
        verts.append((r * cos(a), y, r * sin(a)))
for j in range(len(mountain_heights) - 1):
    for i in range(96):
        a = j * 96 + i
        b = j * 96 + (i + 1) % 96
        faces.extend([(a, a + 96, b), (b, a + 96, b + 96)])
# Both caps lie inside the body or snow layer. Stopping the blue core below the
# snow summit keeps its old sharp rim from poking through the rounded snowcap.
for j, y in [
    (0, mountain_heights[0]),
    (len(mountain_heights) - 1, mountain_heights[-1]),
]:
    cap = len(verts)
    verts.append((0, y, 0))
    for i in range(96):
        a, b = j * 96 + i, j * 96 + (i + 1) % 96
        faces.append((cap, a, b) if j == 0 else (cap, b, a))
g.mesh("Fuji blue mountain", verts, faces, BLUE)
verts = []
faces = []
snowline = []
snow_rings = 27
for j in range(snow_rings):
    for i in range(96):
        a = 2 * PI * i / 96
        bottom = 2.880 + 0.024 * cos(3 * a + 0.8) + 0.01 * cos(5 * a)
        if j <= 18:
            y = bottom + (3.020 - bottom) * j / 18
            r = mountain_radius(y) + 0.002
        else:
            t = (j - 18) / 8
            u = 1 - t
            # A 0.02-high quadratic shoulder meets a flat summit tangentially.
            y = u * u * 3.020 + 2 * u * t * 3.040 + t * t * 3.040
            r = (
                u * u * (mountain_radius(3.020) + 0.002)
                + 2 * u * t * 0.120
                + t * t * 0.106
            )
        verts.append((r * cos(a), y, r * sin(a)))
        if j == 0:
            snowline.append((r * cos(a), y, r * sin(a)))
for j in range(snow_rings - 1):
    for i in range(96):
        a = j * 96 + i
        b = j * 96 + (i + 1) % 96
        faces.extend([(a, a + 96, b), (b, a + 96, b + 96)])
# Summit cap.
verts.append((0, 3.04, 0))
cap = len(verts) - 1
for i in range(96):
    faces.append((cap, (snow_rings - 1) * 96 + (i + 1) % 96, (snow_rings - 1) * 96 + i))
g.mesh("Fuji white snowcap", verts, faces, WHITE)
tube("Fuji wavy snowline", snowline, 0.015, INK)

# Rounded three-feather wings: sculpted in the sagittal plane with a puffy
# cross-section and outward slope, preserving the front AND side silhouettes.
wing_contour = bezier(
    (0.18, 0.04),
    [
        ((0.42, -0.02), (0.48, -0.36), (0.36, -0.70)),
        ((0.30, -0.90), (0.16, -0.94), (0.09, -0.76)),
        ((0.04, -0.99), (-0.15, -0.99), (-0.19, -0.78)),
        ((-0.29, -0.93), (-0.47, -0.85), (-0.44, -0.64)),
        ((-0.44, -0.37), (-0.23, 0.12), (0.18, 0.04)),
    ],
    16,
)
for side_index, (side, sign) in enumerate([("Left", -1), ("Right", 1)]):
    n, nr = len(wing_contour), 28
    vertices = []
    # The feather lies alongside the body. A buried, tapered shoulder joins a
    # padded palm, then three round lobes. Both half-surfaces share edge normals.
    for half in [1, -1]:
        for k in range(nr + 1):
            r = k / nr
            for z, y in wing_contour:
                zz = r * z
                yy = -0.40 + r * (y + 0.40)
                shoulder_taper = smooth(-0.30, 0.08, yy)
                xx = sign * (
                    1.045
                    - 0.20 * shoulder_taper
                    + half * 0.14 * sqrt(max(0, 1 - r * r))
                )
                vertices.append((xx, 2.0 + yy, zz))
    faces = []
    halfsize = (nr + 1) * n
    for half in range(2):
        for k in range(nr):
            for i in range(n):
                a = half * halfsize + k * n + i
                b = half * halfsize + k * n + (i + 1) % n
                ts = [(a, b, a + n), (b, b + n, a + n)]
                if (half == 0) == (sign == 1):
                    ts = [(a, c, b) for a, b, c in ts]
                faces.extend(ts)

    def wing_weights(v, i=side_index):
        d = 2.02 - v[1]
        # Split the existing weights across offset flex joints, at most four
        # per vertex. Their rest skin matrices equal their parents', preserving
        # the exact walking deformation while other clips send a travelling
        # bend along the feather instead of hinging it at one fixed crease.
        if d < 0.21:
            w = smooth(-0.02, 0.21, d)
            anchors = [(head, 1 - w), (wing_nodes[i], w)]
        elif d < 0.59:
            w = smooth(0.21, 0.59, d)
            anchors = [(wing_nodes[i], 1 - w), (wing_bends[i], w)]
        else:
            w = smooth(0.59, 0.91, d)
            anchors = [(wing_bends[i], 1 - w), (wing_tips[i], w)]
        splits = {
            wing_nodes[i]: (wing_soft[i][0], 0.70 * smooth(0.12, 0.34, d)),
            wing_bends[i]: (wing_soft[i][1], 0.70 * smooth(0.40, 0.64, d)),
            wing_tips[i]: (wing_soft[i][2], 0.70 * smooth(0.78, 0.96, d)),
        }
        result = []
        for node, weight in anchors:
            if node == head:
                result.append((node, weight))
            else:
                soft, split = splits[node]
                result.extend([(node, weight * (1 - split)), (soft, weight * split)])
        return result

    g.mesh(
        side + " sculpted three-feather wing",
        vertices,
        faces,
        BLUE,
        weights=wing_weights,
    )

# Sagittal samples are the complete foot silhouette for rotations around X.
# Contact fitting uses these authored points, including the blended bend zones.
foot_profiles = []
for i, (side, x) in enumerate([("Left", -0.29), ("Right", 0.29)]):
    vertices, faces = [], []
    segments, rings = 64, 44
    # A continuous soft leg avoids exposed ball joints. Its end disappears into
    # the rounded foot and its upper cap is buried safely inside the body.
    for j in range(rings + 1):
        t = j / rings
        y = 0.16 + 0.54 * t
        radius = 0.097 + 0.011 * cos(PI * t)
        for k in range(segments):
            a = 2 * PI * k / segments
            vertices.append((x + radius * cos(a), y, 0.02 + radius * sin(a)))
    for j in range(rings):
        for k in range(segments):
            a, b = j * segments + k, j * segments + (k + 1) % segments
            faces.extend([(a, a + segments, b), (b, a + segments, b + segments)])

    def leg_weights(v, i=i):
        if v[1] > 0.405:
            w = smooth(0.405, 0.64, v[1])
            return [(knees[i], 1 - w), (legs[i], w)]
        w = smooth(0.17, 0.405, v[1])
        return [(ankles[i], 1 - w), (knees[i], w)]

    g.mesh(side + " flexible leg", vertices, faces, BROWN, weights=leg_weights)

    def foot_weights(v, i=i):
        # A wide, smooth ball transition avoids a toy hinge. The short toe
        # segment curls independently while the rear sole follows the ankle.
        ball = smooth(0.13, 0.32, v[2])
        tip = smooth(0.32, 0.46, v[2])
        return [
            (ankles[i], 1 - ball),
            (forefeet[i], ball * (1 - tip)),
            (toes[i], ball * tip),
        ]

    ellipsoid(
        side + " rounded foot",
        (x * 1.12, 0.17, 0.16),
        (0.23, 0.168, 0.32),
        BROWN,
        segments=96,
        rings=56,
        weights=foot_weights,
    )
    profile = []
    for j in range(57):
        lat = PI * j / 56
        # At each latitude, every ring point lies between these two extrema
        # in Z. Include the full ring because a flexed sole can have its
        # lowest point inside a blend zone, away from its outline.
        for k in range(49):
            z = 0.16 + 0.32 * sin(lat) * cos(PI * k / 48)
            y = 0.17 + 0.168 * cos(lat)
            profile.append(
                (y - 0.17, z - 0.02, tuple(w for _, w in foot_weights((x, y, z))))
            )
    foot_profiles.append(profile)

# Short raised fan on the back, visibly projecting beyond the body in profile.
verts = []
faces = []
tail_sections = []
# The closed root is buried inside the body. The visible fan retains its width,
# lift and short projection while its far edge rounds over instead of ending
# in an open tube.
root_height = 0.09 * sin(PI * 0.08)
for j in range(9):
    a = PI * 0.5 * j / 8
    tail_sections.append((0.16 * sin(a), root_height * sin(a), 0.02, 0.085 * cos(a)))
for j in range(1, 33):
    t = 0.96 * j / 32
    width = 0.16 + 0.16 * sin(t * PI * 0.72)
    cy = 0.02 - 0.10 * sin(t * PI) + 0.10 * t
    cz = -0.40 * t
    height = 0.09 * sin(PI * (0.08 + 0.84 * t))
    tail_sections.append((width, height, cy, cz))
width, height, cy, cz = tail_sections[-1]
for j in range(1, 13):
    a = PI * 0.5 * j / 12
    tail_sections.append(
        (
            width * cos(a),
            height * cos(a),
            cy + (0.12 - cy) * sin(a),
            cz - 0.016 * sin(a),
        )
    )
for width, height, cy, cz in tail_sections:
    for i in range(48):
        a = 2 * PI * i / 48
        verts.append((width * cos(a), cy + height * sin(a), cz))
for j in range(len(tail_sections) - 1):
    for i in range(48):
        a = j * 48 + i
        b = j * 48 + (i + 1) % 48
        faces.extend([(a, a + 48, b), (b, a + 48, b + 48)])
g.mesh("Blue raised tail fan", verts, faces, BLUE, tail)


def quat(axis, angle):
    return tuple(sin(angle / 2) * v for v in axis) + (cos(angle / 2),)


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def animate(name, duration, samples, pose):
    times = [duration * i / samples for i in range(samples + 1)]
    poses = [pose(t / duration) for t in times]
    # All clips key every animated property, including rest values. This prevents
    # stale limb/eyelid poses when switching clips in glTF animation players.
    tracks = []
    for node, path in poses[0]:
        tracks.append((node, path, times, [p[(node, path)] for p in poses]))
    g.clip(name, tracks)


def rest():
    pose = {(0, "translation"): (0, 0, 0)}
    for n in joints:
        pose[(n, "translation")] = tuple(g.doc["nodes"][n]["translation"])
        pose[(n, "rotation")] = quat((1, 0, 0), 0)
        pose[(n, "scale")] = (1, 1, 1)
    for n in eyes:
        pose[(n, "scale")] = (1, 1, 1)
    for n in lids:
        pose[(n, "scale")] = (0.001, 0.001, 0.001)
    return pose


def bend_body(p, bob=0, lean=0, nod=0, breathe=0):
    p[(hips, "translation")] = (0, 0.68 + bob, 0)
    p[(hips, "scale")] = (1 + breathe * 0.25, 1 - breathe * 0.35, 1 + breathe * 0.20)
    p[(torso, "rotation")] = quat((0, 0, 1), lean)
    p[(head, "rotation")] = quat((1, 0, 0), nod)
    p[(torso, "scale")] = (1 + breathe * 0.30, 1 - breathe * 0.25, 1 + breathe * 0.25)


def plant_leg(p, i, foot_y=0.17, foot_z=0.02, hip_bob=0, pitch=0, hip_x=0):
    # Solve a two-bone chain in a plane that tilts towards the planted foot.
    # This lets the hips transfer weight sideways without dragging the sole.
    hip_y = 0.64 + hip_bob
    dx, dy, dz = -hip_x, foot_y - hip_y, foot_z - 0.02
    side_tilt = math.atan2(dx, -dy)
    plane_y = -sqrt(dx * dx + dy * dy)
    d = sqrt(plane_y * plane_y + dz * dz)
    stretch = max(1, d / 0.4699)
    length = 0.235 * stretch
    aim = math.atan2(-dz, -plane_y)
    flex = math.acos(max(-1, min(1, d / (2 * length))))
    upper, lower = aim - flex, 2 * flex
    hip_rotation = qmul(quat((0, 0, 1), side_tilt), quat((1, 0, 0), upper))
    knee_rotation = quat((1, 0, 0), lower)
    leg_rotation = qmul(hip_rotation, knee_rotation)
    inverse_leg = tuple(-v for v in leg_rotation[:3]) + (leg_rotation[3],)
    p[(legs[i], "translation")] = (bind_positions[legs[i]][0] + hip_x, hip_y, 0.02)
    p[(legs[i], "rotation")] = hip_rotation
    p[(knees[i], "translation")] = (0, -length, 0)
    p[(knees[i], "rotation")] = knee_rotation
    p[(ankles[i], "translation")] = (0, -length, 0)
    p[(ankles[i], "rotation")] = qmul(inverse_leg, quat((1, 0, 0), pitch))


def foot_clearance(i, pitch, ball, tip):
    """Find the actual skinned sole height before placing the ankle."""
    cp, sp, cb, sb, ct, st = (
        cos(pitch),
        sin(pitch),
        cos(ball),
        sin(ball),
        cos(tip),
        sin(tip),
    )
    ball_y, ball_z = -0.065, 0.23
    tip_y, tip_z = -0.07, 0.365
    bottom = 1
    for y, z, (ankle_weight, ball_weight, tip_weight) in foot_profiles[i]:
        by = ball_y + cb * (y - ball_y) - sb * (z - ball_z)
        bz = ball_z + sb * (y - ball_y) + cb * (z - ball_z)
        ty = tip_y + ct * (y - tip_y) - st * (z - tip_z)
        tz = tip_z + st * (y - tip_y) + ct * (z - tip_z)
        ty, tz = (
            ball_y + cb * (ty - ball_y) - sb * (tz - ball_z),
            ball_z + sb * (ty - ball_y) + cb * (tz - ball_z),
        )
        blended_y = ankle_weight * y + ball_weight * by + tip_weight * ty
        blended_z = ankle_weight * z + ball_weight * bz + tip_weight * tz
        bottom = min(bottom, cp * blended_y - sp * blended_z)
    return -bottom + 0.002


def gait_foot(
    p, i, stride, stance, reach, lift_height, hip_bob, hip_x=0, running=False
):
    """Heel contact, flat support, toe push-off, then a curled recovery."""
    heel_angle, push_angle = (0.20, 0.85) if running else (0.24, 0.62)
    if stride < stance:
        progress = stride / stance
        push = smooth(0.55, 1, progress)
        pitch = -heel_angle * (1 - smooth(0, 0.27, progress)) + push_angle * push
        ball, tip = -0.90 * push_angle * push, -0.12 * push
        foot_z = 0.02 + reach * (1 - 2 * progress)
        lift = 0
    else:
        progress = (stride - stance) / (1 - stance)
        release = 1 - smooth(0, 0.43, progress)
        curl = sin(PI * progress) ** 2
        pitch = push_angle + (-heel_angle - push_angle) * smooth(0, 0.70, progress)
        ball = -0.90 * push_angle * release - 0.16 * curl
        tip = -0.12 * release - 0.17 * curl
        foot_z = 0.02 - reach + 2 * reach * smooth(0, 1, progress)
        lift = lift_height * sin(PI * progress) ** 1.65
    p[(forefeet[i], "rotation")] = quat((1, 0, 0), ball)
    p[(toes[i], "rotation")] = quat((1, 0, 0), tip)
    foot_y = foot_clearance(i, pitch, ball, tip) + lift
    plant_leg(p, i, foot_y, foot_z, hip_bob, pitch, hip_x)


def blink_eyes(p, close):
    for n in eyes:
        p[(n, "scale")] = (1, max(0.001, 1 - close), 1)
    lid_scale = max(0.001, smooth(0.65, 0.94, close))
    for n in lids:
        p[(n, "scale")] = (lid_scale,) * 3


def pulse(t, center, width):
    return 1 - smooth(0, width, abs(t - center))


def idle(t):
    p = rest()
    phase = 2 * PI * t
    breath = (1 - cos(phase)) / 2
    bend_body(
        p,
        bob=0.012 * breath,
        lean=0.012 * sin(phase),
        nod=0.018 * sin(phase),
        breathe=-0.07 * breath,
    )
    for i, sign in enumerate([-1, 1]):
        p[(wing_nodes[i], "rotation")] = quat((0, 0, 1), sign * 0.025 * breath)
        p[(wing_bends[i], "rotation")] = quat((1, 0, 0), 0.018 * sin(phase))
    p[(tail, "rotation")] = quat((1, 0, 0), 0.035 * sin(phase))
    jiggle_crest(p, phase, 0.10 * breath)
    blink_eyes(p, pulse(t, 0.70, 0.028))
    return p


def walk(t):
    p = rest()
    # A periodic gait has identical endpoints, without stopping between cycles.
    # The Flutter player blends this moving pose with the other full-body clips.
    envelope = 1
    phase = 2 * PI * t
    bob = -0.028 * envelope * (0.55 + 0.45 * cos(2 * phase))
    bend_body(
        p,
        bob=bob,
        lean=0.038 * envelope * sin(phase),
        nod=-0.018 * envelope * sin(2 * phase),
        breathe=0.025 * envelope,
    )
    for i in range(2):
        step = phase + i * PI
        # Preserve the established 1.4-second cadence and alternating limbs,
        # adding a heel-to-toe contact sequence inside each existing half-cycle.
        stride = (t + 0.75 + i * 0.5) % 1
        gait_foot(p, i, stride, 0.5, 0.15, 0.12, bob)
        p[(wing_nodes[i], "rotation")] = quat((1, 0, 0), -0.11 * sin(step) * envelope)
        p[(wing_bends[i], "rotation")] = quat(
            (1, 0, 0), -0.065 * sin(step - 0.5) * envelope
        )
        p[(wing_tips[i], "rotation")] = quat(
            (1, 0, 0), -0.045 * sin(step - 0.9) * envelope
        )
    p[(tail, "rotation")] = quat((1, 0, 0), 0.04 * sin(2 * phase) * envelope)
    return p


def flex_wing(p, i, phase, strength=1):
    """Delayed alternating curvature runs from the shoulder to the soft tip."""
    sign = -1 if i == 0 else 1
    for node, amount, delay in [
        (wing_bends[i], 0.90, 0.65),
        (wing_tips[i], 0.88, 1.35),
        (wing_soft[i][0], 0.32, 0.25),
        (wing_soft[i][1], 0.42, 0.95),
        (wing_soft[i][2], 0.50, 1.70),
    ]:
        p[(node, "rotation")] = quat(
            (0, 0, 1), sign * strength * amount * sin(phase - delay)
        )


def jiggle_crest(p, phase, strength=1):
    p[(crest, "rotation")] = qmul(
        quat((0, 0, 1), strength * 0.22 * sin(phase - 0.55)),
        quat((1, 0, 0), strength * 0.10 * sin(phase)),
    )
    p[(crest_tip, "rotation")] = quat((0, 0, 1), strength * 0.30 * sin(phase - 1.10))


def jump(t):
    p = rest()
    crouch = pulse(t, 0.14, 0.14)
    air = smooth(0.23, 0.31, t) * (1 - smooth(0.74, 0.81, t))
    flight_t = max(0, min(1, (t - 0.23) / 0.58))
    height = 0.66 * 4 * flight_t * (1 - flight_t)
    land = pulse(t, 0.85, 0.10)
    flap_phase = 2 * PI * 5 * (t - 0.20) / 0.65
    wings = smooth(0.03, 0.22, t) * (1 - smooth(0.81, 0.99, t))
    bob = -0.105 * crouch - 0.095 * land
    bend_body(
        p,
        bob=bob,
        nod=0.085 * crouch - 0.055 * air,
        breathe=0.23 * crouch + 0.22 * land - 0.07 * air,
    )
    p[(head, "scale")] = (1 + 0.055 * land, 1 - 0.07 * land, 1 + 0.035 * land)
    p[(0, "translation")] = (0, height, 0)
    for i, sign in enumerate([-1, 1]):
        shoulder = wings * (1.02 + 0.83 * cos(flap_phase))
        p[(wing_nodes[i], "rotation")] = quat((0, 0, 1), sign * shoulder)
        flex_wing(p, i, flap_phase, wings)
        plant_leg(p, i, 0.17 + 0.11 * air, 0.02 - 0.075 * air, bob, -0.16 * air)
    p[(tail, "rotation")] = quat((1, 0, 0), -0.17 * air + 0.12 * land)
    jiggle_crest(p, flap_phase, 0.35 * wings + 0.6 * land)
    blink_eyes(p, 0.85 * land)
    return p


def run(t):
    p = rest()
    phase = 2 * PI * t
    step_phase = 2 * phase
    bob = -0.045 + 0.03 * cos(step_phase)
    # A short flight interval separates each planted, heavy-footed step.
    stride = t % 0.5
    flight = 0.07 * sin(PI * (stride - 0.34) / 0.16) ** 2 if stride > 0.34 else 0
    p[(0, "translation")] = (0, flight, 0)
    weight_shift = cos(phase - 0.34 * PI)
    hip_x = -0.115 * weight_shift
    bend_body(
        p,
        bob=bob,
        lean=0.145 * weight_shift,
        nod=0.15 + 0.035 * sin(step_phase),
        breathe=0.10 * cos(step_phase),
    )
    p[(hips, "translation")] = (hip_x, 0.68 + bob, 0)
    p[(torso, "rotation")] = qmul(p[(torso, "rotation")], quat((1, 0, 0), 0.09))
    # The head catches up a little later, keeping the face readable as the
    # body rocks over each supporting leg in a small, determined trot.
    p[(head, "rotation")] = qmul(
        quat((0, 0, 1), -0.095 * cos(phase - 0.43 * PI)),
        p[(head, "rotation")],
    )
    p[(head, "scale")] = (1 + 0.025 * cos(step_phase), 1 - 0.035 * cos(step_phase), 1)
    for i, sign in enumerate([-1, 1]):
        stride = (t + i * 0.5) % 1
        gait_foot(p, i, stride, 0.34, 0.23, 0.22, bob, hip_x, running=True)
        p[(wing_nodes[i], "rotation")] = qmul(
            quat((0, 0, 1), sign * (0.75 + 0.57 * sin(step_phase))),
            quat((1, 0, 0), -0.18),
        )
        flex_wing(p, i, step_phase, 0.85)
    p[(tail, "rotation")] = quat((1, 0, 0), 0.13 * sin(step_phase - 0.6))
    jiggle_crest(p, step_phase, 0.60)
    return p


def shake(t):
    p = rest()
    envelope = smooth(0, 0.16, t) * (1 - smooth(0.73, 1, t))
    phase = 2 * PI * 3.5 * t
    bob = -0.018 * envelope * (1 - cos(2 * phase))
    bend_body(
        p,
        bob=bob,
        lean=0.14 * envelope * sin(phase),
        breathe=0.18 * envelope * sin(2 * phase),
    )
    p[(hips, "translation")] = (0.045 * envelope * sin(phase), 0.68 + bob, 0)
    p[(head, "rotation")] = qmul(
        quat((0, 1, 0), 0.46 * envelope * sin(phase - 0.25)),
        quat((0, 0, 1), -0.065 * envelope * sin(phase - 0.65)),
    )
    p[(head, "scale")] = (
        1 + 0.05 * envelope * sin(2 * phase),
        1 - 0.04 * envelope * sin(2 * phase),
        1,
    )
    for i, sign in enumerate([-1, 1]):
        p[(wing_nodes[i], "rotation")] = quat(
            (0, 0, 1), sign * 0.14 * envelope * (1 + sin(phase))
        )
        flex_wing(p, i, phase + i * PI, 0.48 * envelope)
        plant_leg(p, i, hip_bob=bob)
    p[(tail, "rotation")] = quat((0, 1, 0), 0.19 * envelope * sin(phase - 0.8))
    jiggle_crest(p, phase, 1.2 * envelope)
    return p


def wave(t):
    p = rest()
    envelope = smooth(0, 0.22, t) * (1 - smooth(0.78, 1, t))
    phase = 2 * PI * 3 * t
    bend_body(
        p,
        bob=-0.014 * envelope,
        lean=-0.075 * envelope,
        nod=0.025 * sin(phase) * envelope,
        breathe=0.10 * envelope,
    )
    # The shoulder raises the wing once; middle and tip follow the wave with
    # delayed curves, keeping the rooted edge on the body throughout the arc.
    p[(wing_nodes[1], "rotation")] = qmul(
        quat((0, 0, 1), envelope * (1.62 + 0.10 * sin(phase))),
        quat((0, 1, 0), -0.95 * envelope),
    )
    flex_wing(p, 1, phase, 1.05 * envelope)
    jiggle_crest(p, phase, 0.25 * envelope)
    p[(wing_nodes[0], "rotation")] = quat((0, 0, 1), -0.07 * envelope)
    p[(wing_bends[0], "rotation")] = quat((1, 0, 0), 0.05 * sin(phase) * envelope)
    for i in range(2):
        plant_leg(p, i, hip_bob=-0.014 * envelope)
    blink_eyes(p, pulse(t, 0.67, 0.035))
    return p


def blink(t):
    p = idle(t)
    blink_eyes(p, max(pulse(t, 0.34, 0.085), pulse(t, 0.62, 0.075)))
    return p


def sit(t):
    """Sit down once, then breathe in a seated loop from 2.4 through 6.4 seconds."""
    p = rest()
    if t <= 0:
        return p
    seated = smooth(0.07, 0.32, t)
    feet_out = smooth(0.15, 0.36, t)
    hold = smooth(0.31, 0.375, t)
    # 0.375 * 6.4 = 2.4 seconds. The player repeats only this four-second
    # section after entering, so every joint must meet at the same phase.
    phase = 2 * PI * (((t - 0.375) / 0.625) % 1)
    breathe = seated * 0.075 + hold * 0.015 * sin(phase)
    # The lowest belly vertex is 0.12 below Hips. Compensate its Y scale so
    # seated breathing keeps it 0.006 above the stage instead of hovering.
    bob = -0.554 * seated - 0.042 * breathe
    anticipation = pulse(t, 0.14, 0.14)
    bend_body(
        p,
        bob=bob,
        nod=-0.055 * anticipation + 0.025 * hold * sin(phase - 0.4),
        breathe=breathe,
    )
    p[(torso, "rotation")] = quat((1, 0, 0), 0.16 * anticipation - 0.055 * seated)
    for i, sign in enumerate([-1, 1]):
        # A soft knee remains hidden inside the belly. The short leg extends
        # elastically toward the lifted toes, with both heels still grounded.
        pitch = -0.52 * feet_out
        ball = 0.055 * feet_out + 0.02 * hold * sin(phase - i * 0.3)
        tip = -0.025 * feet_out
        p[(forefeet[i], "rotation")] = quat((1, 0, 0), ball)
        p[(toes[i], "rotation")] = quat((1, 0, 0), tip)
        plant_leg(
            p,
            i,
            foot_y=foot_clearance(i, pitch, ball, tip),
            foot_z=0.02 + 0.68 * feet_out,
            hip_bob=0.78 * bob,
            pitch=pitch,
        )
        p[(wing_nodes[i], "rotation")] = qmul(
            quat((0, 0, 1), sign * (0.10 * seated + 0.18 * anticipation)),
            quat((1, 0, 0), -0.09 * seated),
        )
        flex_wing(p, i, phase, 0.035 * hold)
    p[(tail, "rotation")] = quat((1, 0, 0), -0.16 * seated)
    jiggle_crest(p, phase, 0.065 * hold + 0.10 * anticipation)
    blink_eyes(p, max(pulse(t, 0.56, 0.018), pulse(t, 0.86, 0.018)))
    return p


def planted_gesture(p, bob, phase, softness, wing_lift=0):
    """Keep both soles grounded while the soft upper body settles behind a cue."""
    for i, sign in enumerate([-1, 1]):
        plant_leg(p, i, hip_bob=bob)
        p[(wing_nodes[i], "rotation")] = quat((0, 0, 1), sign * wing_lift)
        flex_wing(p, i, phase - i * 0.12, softness)
    jiggle_crest(p, phase, softness * 1.25)
    p[(tail, "rotation")] = quat((1, 0, 0), 0.09 * softness * sin(phase - 0.4))


def rotate_vector(rotation, vector):
    xyz, w = rotation[:3], rotation[3]
    tangent = cross(xyz, vector)
    turn = vadd(tuple(w * value for value in tangent), cross(xyz, tangent))
    return vadd(vector, tuple(2 * value for value in turn))


def place_balance_leg(p, i, hip_position, foot_position, pitch):
    """Solve each root-level leg beneath the rigid upper body."""
    dx, dy, dz = vsub(foot_position, hip_position)
    side_tilt = math.atan2(dx, -dy)
    plane_y = -sqrt(dx * dx + dy * dy)
    distance = sqrt(plane_y * plane_y + dz * dz)
    length = 0.235 * max(1, distance / 0.4699)
    aim = math.atan2(-dz, -plane_y)
    flex = math.acos(max(-1, min(1, distance / (2 * length))))
    hip_rotation = qmul(quat((0, 0, 1), side_tilt), quat((1, 0, 0), aim - flex))
    knee_rotation = quat((1, 0, 0), 2 * flex)
    leg_rotation = qmul(hip_rotation, knee_rotation)
    inverse_leg = tuple(-value for value in leg_rotation[:3]) + (leg_rotation[3],)
    p[(legs[i], "translation")] = hip_position
    p[(legs[i], "rotation")] = hip_rotation
    p[(knees[i], "translation")] = (0, -length, 0)
    p[(knees[i], "rotation")] = knee_rotation
    p[(ankles[i], "translation")] = (0, -length, 0)
    p[(ankles[i], "rotation")] = qmul(inverse_leg, quat((1, 0, 0), pitch))


def front_facing_body(p, shift, bob, lean, foot_offsets=(0, 0), lifts=(0, 0)):
    """Keep the roundel facing front and rigid while the feet make small steps."""
    rotation = quat((0, 0, 1), lean)
    position = (shift, 0.68 + bob, 0)
    p[(hips, "translation")] = position
    p[(hips, "rotation")] = rotation
    for i, sign in enumerate([-1, 1]):
        lift = lifts[i]
        hip_offset = vsub(bind_positions[legs[i]], bind_positions[hips])
        hip_position = vadd(position, rotate_vector(rotation, hip_offset))
        pitch = -0.08 * lift
        rest_x = bind_positions[legs[i]][0]
        foot_position = (
            rest_x + foot_offsets[i],
            foot_clearance(i, pitch, 0, 0) + 0.10 * lift,
            0.02,
        )
        place_balance_leg(p, i, hip_position, foot_position, pitch)


def nod(t):
    """Two enthusiastic full-body nods, each led by a small upward anticipation."""
    p = rest()
    envelope = smooth(0.02, 0.15, t) * (1 - smooth(0.82, 0.99, t))
    first, second = pulse(t, 0.31, 0.20), pulse(t, 0.66, 0.21)
    anticipation = pulse(t, 0.10, 0.09) + pulse(t, 0.49, 0.10)
    dip = 0.50 * first + 0.44 * second - 0.12 * anticipation
    bob = -0.080 * first - 0.070 * second + 0.018 * anticipation
    bend_body(p, bob=bob, nod=dip, breathe=0.12 * (first + second))
    p[(torso, "rotation")] = quat(
        (1, 0, 0), 0.19 * first + 0.16 * second - 0.04 * anticipation
    )
    planted_gesture(p, bob, 2 * PI * 2 * t, 0.24 * envelope, 0.14 * envelope)
    return p


def tilt(t):
    """Bring one wing beside the cheek and ponder, keeping both feet grounded."""
    p = rest()
    envelope = smooth(0.08, 0.30, t) * (1 - smooth(0.72, 0.98, t))
    hand = smooth(0.13, 0.36, t) * (1 - smooth(0.68, 0.95, t))
    pondering = 0.012 * sin(2 * PI * t) * envelope
    front_facing_body(
        p,
        shift=-0.055 * envelope,
        bob=-0.015 * envelope,
        lean=-0.15 * envelope + pondering,
    )
    phase = 2 * PI * 1.5 * t
    p[(wing_nodes[0], "rotation")] = quat((0, 0, 1), -0.10 * envelope)
    flex_wing(p, 0, phase, 0.035 * envelope)
    # Sweep forward first, then curl up beside the cheek; the central bib and
    # roundel stay uncovered instead of getting squeezed by a torso twist.
    p[(wing_nodes[1], "rotation")] = qmul(
        quat((0, 1, 0), -0.36 * hand), quat((1, 0, 0), -1.16 * hand)
    )
    p[(wing_bends[1], "rotation")] = quat((1, 0, 0), -0.12 * hand)
    p[(wing_tips[1], "rotation")] = quat((1, 0, 0), -0.10 * hand)
    jiggle_crest(p, phase, 0.07 * envelope)
    blink_eyes(p, pulse(t, 0.58, 0.026))
    return p


def bow(t):
    """Stand tall, make a deep deliberate bow, hold it, then slowly recover."""
    p = rest()
    down = smooth(0.12, 0.39, t) * (1 - smooth(0.60, 0.96, t))
    anticipation = pulse(t, 0.095, 0.095)
    bob = -0.105 * down + 0.035 * anticipation
    bend_body(p, bob=bob, nod=0.34 * down, breathe=0.085 * down)
    p[(torso, "rotation")] = quat((1, 0, 0), 0.67 * down - 0.10 * anticipation)
    planted_gesture(p, bob, 2 * PI * 1.5 * t, 0.20 * down, 0.23 * down)
    # The wings trail the bow slightly, close to the body instead of sweeping
    # across the face; the weighted belly remains supported by the bent legs.
    for i in range(2):
        p[(wing_nodes[i], "rotation")] = qmul(
            p[(wing_nodes[i], "rotation")], quat((1, 0, 0), -0.35 * down)
        )
    return p


def celebrate(t):
    """Two distinct joyful jumps, with tucked feet and soft, fully planted landings."""
    p = rest()
    envelope = smooth(0.025, 0.18, t) * (1 - smooth(0.82, 0.99, t))
    # Root-space parabolas leave a clearly grounded interval between the hops.
    # The second leap is slightly higher, building to the final "hooray" pose.
    height, air = 0, 0
    for start, end, peak in ((0.17, 0.43, 0.62), (0.51, 0.75, 0.72)):
        if start < t < end:
            progress = (t - start) / (end - start)
            height += peak * 4 * progress * (1 - progress)
        air += smooth(start, start + 0.055, t) * (1 - smooth(end - 0.055, end, t))
    crouch = pulse(t, 0.105, 0.105)
    land = pulse(t, 0.455, 0.065) + pulse(t, 0.79, 0.085)
    bob = -0.115 * crouch - 0.120 * land
    bend_body(
        p,
        bob=bob,
        lean=0.075 * sin(2 * PI * 2 * t) * envelope,
        nod=-0.12 * air + 0.10 * crouch,
        breathe=0.24 * crouch + 0.26 * land - 0.10 * air,
    )
    p[(0, "translation")] = (0, height, 0)
    p[(head, "scale")] = (
        1 + 0.045 * land,
        1 - 0.065 * land + 0.025 * air,
        1 + 0.025 * land,
    )
    phase = 2 * PI * 4 * t
    for i, sign in enumerate([-1, 1]):
        p[(wing_nodes[i], "rotation")] = qmul(
            quat((0, 0, 1), sign * envelope * (2.42 + 0.16 * sin(phase))),
            quat((0, 1, 0), -sign * 0.20 * envelope),
        )
        flex_wing(p, i, phase, 0.35 * envelope)
        plant_leg(p, i, 0.17 + 0.13 * air, 0.02 - 0.075 * air, bob, -0.18 * air)
    p[(tail, "rotation")] = quat((1, 0, 0), -0.20 * air + 0.15 * land)
    jiggle_crest(p, phase, 0.35 * envelope + 0.50 * land)
    return p


def stretch(t):
    """Reach both wings overhead, lengthen and arch the body, then flop softly down."""
    p = rest()
    reach = smooth(0.07, 0.38, t) * (1 - smooth(0.64, 0.96, t))
    prepare = pulse(t, 0.12, 0.12)
    release = pulse(t, 0.84, 0.14)
    bob = 0.10 * reach - 0.085 * prepare - 0.075 * release
    bend_body(
        p,
        bob=bob,
        nod=-0.14 * reach + 0.12 * release,
        breathe=-0.30 * reach + 0.18 * (prepare + release),
    )
    p[(torso, "rotation")] = quat((1, 0, 0), -0.13 * reach + 0.08 * release)
    p[(head, "scale")] = (1 - 0.035 * reach, 1 + 0.055 * reach, 1 - 0.035 * reach)
    softness = 0.12 * reach + 0.36 * release
    planted_gesture(p, bob, 2 * PI * 1.75 * t, softness, 2.65 * reach)
    for i in range(2):
        p[(wing_nodes[i], "rotation")] = qmul(
            p[(wing_nodes[i], "rotation")], quat((1, 0, 0), -0.10 * reach)
        )
    return p


# Sampled smooth curves are portable to glTF players and Flutter Scene. Gestures
# return to bind pose; walking stays in its continuous periodic gait, and Sit
# keeps its seated pose for the player to repeat its 2.4–6.4 second hold.
for name, duration, samples, pose in [
    ("Walk", 1.4, 84, walk),
    ("Jump", 2.4, 192, jump),
    ("Wave", 3.2, 192, wave),
    ("Blink", 2.2, 132, blink),
    ("Idle", 4.8, 288, idle),
    ("Run", 0.76, 92, run),
    ("Shake", 2.8, 196, shake),
    ("Sit", 6.4, 256, sit),
    ("Nod", 2.6, 156, nod),
    ("Tilt", 3.4, 204, tilt),
    ("Bow", 3.2, 192, bow),
    ("Celebrate", 3.0, 180, celebrate),
    ("Stretch", 4.0, 240, stretch),
]:
    animate(
        name,
        duration,
        samples,
        pose
        if name in {"Walk", "Run", "Sit"}
        else lambda t, fn=pose: rest() if t <= 0 or t >= 1 else fn(t),
    )
polish_materials(g.doc)
g.save()

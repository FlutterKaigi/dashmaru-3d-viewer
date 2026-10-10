"""Reference-based, curved face markings for the Dashmaru glTF sculpture.

The drawing references use the same round eye outlines for happy arches and
dizzy spirals. A tightly squeezed pair of eyelids adds an exertion expression.
Geometry stays a rigid child of Head,
matching the normal eyes while the soft body bends around it. The Flutter app
selects the visible group independently of the animation channels.
"""

import math


def eye_ink_contour(x, y, circle):
    """Keep the original eye silhouette without overlapping black disks.

    The two outlines meet at the bridge of the nose. Their original ellipses
    overlap by 0.006, which creates competing coplanar triangles. Clip only that
    hidden overlap to the shared centerline; the visible outer contour stays put.
    """
    contour = circle(x, y, 0.170, 0.158)
    sign = -1 if x < 0 else 1
    clipped = []
    previous = contour[-1]
    for current in contour:
        previous_inside = sign * previous[0] >= 0
        current_inside = sign * current[0] >= 0
        if previous_inside != current_inside:
            fraction = -previous[0] / (current[0] - previous[0])
            clipped.append((0.0, previous[1] + fraction * (current[1] - previous[1])))
        if current_inside:
            clipped.append(current)
        previous = current
    return clipped


def build_expressions(g, head, head_position, patch, tube, surface, circle, ink, white):
    """Add hidden smile, spiral and strain groups; return their IDs.

    All contour coordinates are authored in model space and converted to Head
    local space exactly once. Groups start scaled down for generic glTF viewers;
    the Flutter expression selector restores the selected group's unit scale.
    """
    groups = []
    for expression in ("Smile", "Spiral"):
        group = g.node("Face" + expression, head, (0, 0, 0))
        g.doc["nodes"][group]["scale"] = [0.001, 0.001, 0.001]
        groups.append(group)
        for side, x in (("Left", -0.167), ("Right", 0.167)):
            y = 1.81
            prefix = expression + " " + side
            for name, radii, material, offset in (
                ("eye ink", (0.170, 0.158), ink, 0.029),
                ("eye white", (0.134, 0.126), white, 0.034),
            ):
                patch(
                    prefix + " " + name,
                    eye_ink_contour(x, y, circle)
                    if name == "eye ink"
                    else circle(x, y, *radii),
                    material,
                    offset,
                    group,
                    head_position,
                    center=(x, y),
                    rings=8,
                )

            if expression == "Smile":
                # clap.PNG: round, upward arches inside the white of each eye.
                points = [
                    (
                        x + 0.063 * math.cos(math.pi * i / 48),
                        y - 0.030 + 0.077 * math.sin(math.pi * i / 48),
                    )
                    for i in range(49)
                ]
                radius = 0.0185
            else:
                # guruguru.PNG: an open spiral, with space between the turns so
                # the pupil remains readable at the demo's normal camera size.
                points = []
                for i in range(105):
                    t = i / 104
                    angle = -0.60 * math.pi + 2.35 * math.pi * t
                    # The inner curvature must remain wider than the tube, or
                    # the swept surface folds through itself at the first turn.
                    r = 0.019 + 0.072 * t
                    points.append((x + r * math.cos(angle), y + r * math.sin(angle)))
                radius = 0.0145

            stroke_points = [surface(px, py, 0.055) for px, py in points]
            tube(
                prefix + " expression stroke",
                stroke_points,
                radius,
                ink,
                group,
                closed=False,
                origin=head_position,
            )
            # The shared tube helper leaves open ends. Small rounded caps make
            # the embroidered strokes continuous from an oblique camera too.
            for end, center in enumerate((stroke_points[0], stroke_points[-1])):
                _round_cap(
                    g,
                    prefix + " stroke cap " + str(end),
                    center,
                    radius,
                    ink,
                    group,
                    head_position,
                )
    groups.append(_build_strain(g, head, head_position, tube, surface, ink))
    return groups


def _build_strain(g, head, head_position, tube, surface, ink):
    """Squeeze both eyes inward into rounded > < shapes on the blue mask."""
    group = g.node("FaceStrain", head, (0, 0, 0))
    g.doc["nodes"][group]["scale"] = [0.001, 0.001, 0.001]
    # C1-continuous arcs retain the > < silhouette, with the same endpoints and
    # inward tip. Their minimum curvature radius is 0.032, safely above the
    # 0.020 stroke radius: a tighter bend turns the inner tube inside out.
    # No eye whites remain visible when the lids squeeze shut.
    curves = (
        ((-0.100, 0.085), (0.015, 0.080), (0.065, 0.040)),
        ((0.065, 0.040), (0.115, 0.000), (0.065, -0.040)),
        ((0.065, -0.040), (0.015, -0.080), (-0.100, -0.085)),
    )
    for side, x, direction in (("Left", -0.167, 1), ("Right", 0.167, -1)):
        points = []
        for start, control, end in curves:
            for i in range(24):
                t = i / 24
                u = 1 - t
                dx, dy = (
                    u * u * start[k] + 2 * u * t * control[k] + t * t * end[k]
                    for k in range(2)
                )
                points.append(surface(x + direction * dx, 1.81 + dy, 0.055))
        dx, dy = curves[-1][-1]
        points.append(surface(x + direction * dx, 1.81 + dy, 0.055))
        radius = 0.020
        tube(
            "Strain " + side + " squeezed eyelid",
            points,
            radius,
            ink,
            group,
            closed=False,
            origin=head_position,
        )
        for end, center in enumerate((points[0], points[-1])):
            _round_cap(
                g,
                "Strain " + side + " stroke cap " + str(end),
                center,
                radius,
                ink,
                group,
                head_position,
            )
    return group


def _round_cap(g, name, center, radius, material, parent, origin):
    """A small smooth sphere closes the end of an embroidered eye stroke."""
    segments, rings = 20, 12
    vertices, faces = [], []
    for j in range(rings + 1):
        latitude = math.pi * j / rings
        for i in range(segments):
            longitude = 2 * math.pi * i / segments
            delta = (
                radius * math.sin(latitude) * math.cos(longitude),
                radius * math.cos(latitude),
                radius * math.sin(latitude) * math.sin(longitude),
            )
            vertices.append(tuple(center[k] + delta[k] - origin[k] for k in range(3)))
    for j in range(rings):
        for i in range(segments):
            a = j * segments + i
            b = j * segments + (i + 1) % segments
            faces.extend(((a, b, a + segments), (b, b + segments, a + segments)))
    g.mesh(name, vertices, faces, material, parent)

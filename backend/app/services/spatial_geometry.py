"""Canonical normalized image geometry; no inference, storage, or GIS dependencies."""
import math

EPSILON = 1e-10


def cross(a, b, p):
    return (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)


def on_segment(a, b, p):
    return (abs(cross(a, b, p)) <= EPSILON
            and min(a.x, b.x) - EPSILON <= p.x <= max(a.x, b.x) + EPSILON
            and min(a.y, b.y) - EPSILON <= p.y <= max(a.y, b.y) + EPSILON)


def intersects(a, b, c, d):
    if any((on_segment(a, b, c), on_segment(a, b, d),
            on_segment(c, d, a), on_segment(c, d, b))):
        return True
    return (cross(a, b, c) * cross(a, b, d) < 0
            and cross(c, d, a) * cross(c, d, b) < 0)


def validate_polygon(points):
    if not 3 <= len(points) <= 50:
        raise ValueError("Use 3 to 50 polygon vertices")
    if any(not math.isfinite(v) or not 0 <= v <= 1 for p in points for v in (p.x, p.y)):
        raise ValueError("Coordinates must be finite and within [0, 1]")
    if len({(p.x, p.y) for p in points}) != len(points):
        raise ValueError("Duplicate vertices are not allowed; closing vertex is implicit")
    edges = list(zip(points, points[1:] + points[:1]))
    area = abs(sum(a.x * b.y - b.x * a.y for a, b in edges)) / 2
    if area <= EPSILON:
        raise ValueError("Polygon must have non-zero area (greater than 1e-10)")
    for i, (a, b) in enumerate(edges):
        c = points[(i + 2) % len(points)]
        if on_segment(a, b, c) or on_segment(b, c, a):
            raise ValueError("Adjacent edges must not overlap")
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if intersects(a, b, *edges[j]):
                raise ValueError("Polygon must not self-intersect or touch itself")
    return points


def contains(points, p):
    """Even/odd ray casting; edges and vertices within 1e-10 count inside."""
    inside = False
    for a, b in zip(points, points[1:] + points[:1]):
        if on_segment(a, b, p):
            return True
        if (a.y > p.y) != (b.y > p.y):
            if p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x:
                inside = not inside
    return inside


def foot_point(box, width, height):
    """Return normalized clipped bottom-center, or None for no image intersection."""
    if not all(math.isfinite(v) for v in (width, height)) or width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be finite and positive")
    if not all(math.isfinite(v) for v in (box.x1, box.y1, box.x2, box.y2)):
        raise ValueError("Box coordinates must be finite")
    x1, x2 = max(0, box.x1), min(width, box.x2)
    y1, y2 = max(0, box.y1), min(height, box.y2)
    if x1 >= x2 or y1 >= y2:
        return None
    return ((x1 + x2) / (2 * width), y2 / height)

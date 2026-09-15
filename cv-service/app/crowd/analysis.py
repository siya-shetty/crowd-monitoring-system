"""Image-space geometry only: no calibration, masks, or extra inference."""
import math
from statistics import mean


def clipped_rectangles(boxes, width: int, height: int) -> list[tuple[float, float, float, float]]:
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive")
    rectangles = []
    for box in boxes:
        values = (box.x1, box.y1, box.x2, box.y2)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Non-finite rectangle")
        x1, y1, x2, y2 = values
        x1, x2 = max(0., x1), min(float(width), x2)
        y1, y2 = max(0., y1), min(float(height), y2)
        # Reversed, degenerate, or wholly outside rectangles cover no pixels.
        if x2 > x1 and y2 > y1:
            rectangles.append((x1, y1, x2, y2))
    return rectangles


def image_occupancy(boxes, width: int, height: int) -> float:
    """Exact continuous rectangle union via x slabs and merged y intervals.

    O(n^2 log n) time, O(n) temporary memory; independent of image resolution.
    """
    rectangles = clipped_rectangles(boxes, width, height)
    edges = sorted({x for r in rectangles for x in (r[0], r[2])})
    area = 0.
    for left, right in zip(edges, edges[1:]):
        intervals = sorted((y1, y2) for x1, y1, x2, y2 in rectangles if x1 < right and x2 > left)
        covered, end = 0., 0.
        for low, high in intervals:
            covered += max(0., high - max(low, end))
            end = max(end, high)
        area += (right - left) * covered
    return min(1., max(0., area / (width * height)))


def crowd_concentration(boxes, width: int, height: int) -> float:
    """1 - sqrt(2 * (population variance x + population variance y)).

    Centers are normalized to [0,1]; the sum of variances is at most 1/2.
    Fewer than two valid boxes return zero, including a single large box.
    """
    rectangles = clipped_rectangles(boxes, width, height)
    if len(rectangles) < 2:
        return 0.
    xs = [(r[0] + r[2]) / (2 * width) for r in rectangles]
    ys = [(r[1] + r[3]) / (2 * height) for r in rectangles]
    mx, my = mean(xs), mean(ys)
    variance = mean([(x - mx) ** 2 + (y - my) ** 2 for x, y in zip(xs, ys)])
    return min(1., max(0., 1 - math.sqrt(2 * variance)))

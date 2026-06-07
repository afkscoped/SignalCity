"""
algorithms/geometry.py — Computational geometry algorithms for Signal City.
Graham scan (convex hull) and First-Fit Decreasing (bin packing).
"""

import math


def graham_scan(points: list[tuple]) -> list[tuple]:
    """
    Convex hull via Graham scan. Returns hull points in CCW order.
    Used for computing city boundary polygon.
    """
    if len(points) < 3:
        return list(points)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    # Find lowest point (break ties by x)
    anchor = min(points, key=lambda p: (p[1], p[0]))

    def polar_angle(p):
        dx = p[0] - anchor[0]
        dy = p[1] - anchor[1]
        return math.atan2(dy, dx)

    def distance(p):
        return (p[0] - anchor[0]) ** 2 + (p[1] - anchor[1]) ** 2

    sorted_points = sorted(
        [p for p in points if p != anchor],
        key=lambda p: (polar_angle(p), distance(p)),
    )

    hull = [anchor]
    for p in sorted_points:
        while len(hull) > 1 and cross(hull[-2], hull[-1], p) <= 0:
            hull.pop()
        hull.append(p)

    return hull


def first_fit_decreasing(items: list[float], bin_capacity: float):
    """
    Bin packing via First-Fit Decreasing. Generator that yields each placement step.
    items = zone sizes, bin_capacity = district max area.
    """
    sorted_items = sorted(items, reverse=True)
    bins = []  # list of (current_fill, items_in_bin)
    op_count = 0

    for item in sorted_items:
        placed = False
        op_count += 1

        for i, (fill, bin_items) in enumerate(bins):
            if fill + item <= bin_capacity:
                bins[i] = (fill + item, bin_items + [item])
                placed = True

                yield {
                    "kind": "item_placed",
                    "item": item,
                    "bin_idx": i,
                    "bin_fill": round(fill + item, 1),
                    "bin_capacity": bin_capacity,
                    "total_bins": len(bins),
                    "op_count": op_count,
                    "xai_text": f"Placed zone {item:.0f}m² into district {i + 1}. "
                               f"First-fit decreasing: always try the first bin with enough room. "
                               f"Current fill: {fill + item:.1f}/{bin_capacity:.1f}m².",
                }
                break

        if not placed:
            bins.append((item, [item]))
            yield {
                "kind": "item_placed",
                "item": item,
                "bin_idx": len(bins) - 1,
                "bin_fill": item,
                "bin_capacity": bin_capacity,
                "total_bins": len(bins),
                "op_count": op_count,
                "new_bin": True,
                "xai_text": f"No existing district can fit zone {item:.0f}m². "
                           f"Created new district #{len(bins)}. "
                           f"FFD guarantees at most 11/9·OPT + 6/9 bins.",
            }

    yield {
        "kind": "algorithm_done",
        "total_bins": len(bins),
        "total_items": len(sorted_items),
        "bin_fills": [round(f, 1) for f, _ in bins],
        "op_count": op_count,
        "theoretical_complexity": "O(n·log n)",
        "xai_text": f"Bin packing complete. {len(sorted_items)} zones packed into "
                   f"{len(bins)} districts. FFD achieved "
                   f"{sum(f for f, _ in bins) / (len(bins) * bin_capacity) * 100:.0f}% average utilization.",
    }

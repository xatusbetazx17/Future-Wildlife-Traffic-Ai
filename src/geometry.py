"""WGS84 distance and normalized image polygon helpers."""

import math


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a, b, p):
    return (
        abs(cross(a, b, p)) < 1e-12
        and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    )


def intersects(a, b, c, d):
    if any((on_segment(a, b, c), on_segment(a, b, d), on_segment(c, d, a), on_segment(c, d, b))):
        return True
    return (cross(a, b, c) > 0) != (cross(a, b, d) > 0) and (cross(c, d, a) > 0) != (cross(c, d, b) > 0)


def valid_polygon(points):
    if any(len(p) != 2 for p in points) or len({tuple(p) for p in points}) != len(points):
        return False
    area = sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(points, points[1:] + points[:1]))
    if abs(area) < 1e-10:
        return False
    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if intersects(points[i], points[(i + 1) % n], points[j], points[(j + 1) % n]):
                return False
    return True


def inside(point, polygon):
    result = False
    x, y = point
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if on_segment(a, b, point):
            return True
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            result = not result
    return result


def distance_m(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    h = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371008.8 * 2 * math.asin(math.sqrt(min(1, max(0, h))))

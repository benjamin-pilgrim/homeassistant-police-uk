"""Geometry helpers for Police.uk area queries."""
from __future__ import annotations

import math

from .const import MAX_RADIUS_METERS, MIN_RADIUS_METERS, POLYGON_POINTS

_EARTH_RADIUS_M = 6_371_000


def circle_polygon(
    lat: float,
    lng: float,
    radius_m: int,
    points: int = POLYGON_POINTS,
) -> str:
    """Return a Police.uk poly string approximating a circle."""
    if radius_m < MIN_RADIUS_METERS or radius_m > MAX_RADIUS_METERS:
        raise ValueError(
            f"radius_m must be between {MIN_RADIUS_METERS} and {MAX_RADIUS_METERS}"
        )
    if points != POLYGON_POINTS:
        raise ValueError(f"points must be fixed at {POLYGON_POINTS}")

    lat_rad = math.radians(lat)
    lng_rad = math.radians(lng)
    angular_distance = radius_m / _EARTH_RADIUS_M

    vertices: list[str] = []
    for index in range(points):
        bearing = 2 * math.pi * index / points
        vertex_lat = math.asin(
            math.sin(lat_rad) * math.cos(angular_distance)
            + math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing)
        )
        vertex_lng = lng_rad + math.atan2(
            math.sin(bearing) * math.sin(angular_distance) * math.cos(lat_rad),
            math.cos(angular_distance) - math.sin(lat_rad) * math.sin(vertex_lat),
        )

        vertices.append(
            f"{math.degrees(vertex_lat):.6f},{math.degrees(vertex_lng):.6f}"
        )

    return ":".join(vertices)

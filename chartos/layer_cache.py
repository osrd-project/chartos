import pyproj

from typing import Set, Tuple, Optional, Iterator, Collection, Dict, Iterable
from math import floor, pi, tan, atan, sinh, degrees, radians, asinh
from dataclasses import dataclass
from shapely.geometry import Polygon
from shapely.ops import transform
from shapely.prepared import prep
from .config import View, Layer, Field


def get_layer_cache_prefix(layer, version):
    return f"chartis.layer.{layer.name}.version_{version}"


def get_view_cache_prefix(layer, version, view):
    layer_prefix = get_layer_cache_prefix(layer, version)
    return f"{layer_prefix}.{view.name}"


@dataclass(eq=True, frozen=True)
class AffectedTile:
    x: int
    y: int
    z: int

    def to_json(self):
        return {"x": self.x, "y": self.y, "z": self.z}


def get_cache_tile_key(view_prefix: str, tile: AffectedTile):
    return f"{view_prefix}.tile/{tile.z}/{tile.x}/{tile.y}"



def get_xy(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
    n = 2.0 ** zoom
    x = floor((lon + 180.) / 360. * n)
    y = floor((1. - asinh(tan(radians(lat))) / pi) / 2. * n)
    return x, y


def get_nw_deg(z: int, x: int, y: int):
    n = 2.0 ** z
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = atan(sinh(pi * (1 - 2 * y / n)))
    return degrees(lat_rad), lon_deg


def find_prepared_affected_tiles(
        max_zoom,
        prep_geom,
        z: int, x: int, y: int
) -> Iterator[AffectedTile]:
    if z > max_zoom:
        return

    lat_max, long_min = get_nw_deg(z, x, y)
    lat_min, long_max = get_nw_deg(z, x + 1, y + 1)
    bbox = Polygon.from_bounds(long_min, lat_min, long_max, lat_max)
    if not prep_geom.intersects(bbox):
        return

    yield AffectedTile(x, y, z)

    for sub_x in range(x * 2, x * 2 + 2):
        for sub_y in range(y * 2, y * 2 + 2):
            yield from find_prepared_affected_tiles(
                max_zoom,
                prep_geom,
                z + 1,
                sub_x,
                sub_y
            )


pseudo_mercator = pyproj.CRS('EPSG:3857')
gps = pyproj.CRS('EPSG:4326')
pseudo_mercator_to_gps = pyproj.Transformer.from_crs(
    pseudo_mercator, gps, always_xy=True).transform


def find_affected_tiles(max_zoom, geom) -> Iterator[AffectedTile]:
    # chartos works with pseudo mercator everywhere,
    # and eventhough mapbox works with the same projection,
    # the algorithm which finds tiles takes GPS coordinates
    proj_geom = transform(pseudo_mercator_to_gps, geom)
    prepared_geom = prep(proj_geom)
    return find_prepared_affected_tiles(max_zoom, prepared_geom, 0, 0, 0)


async def invalidate_cache(
        redis,
        layer: Layer,
        version: str,
        affected_tiles: Dict[Field, Set[AffectedTile]]
):
    if not affected_tiles:
        return

    def build_evicted_keys() -> Iterable[str]:
        for view in layer.views.values():
            view_affected_tiles = affected_tiles.get(view.on_field)
            if view_affected_tiles is None:
                continue
            cache_location = get_view_cache_prefix(layer, version, view)
            for tile in view_affected_tiles:
                yield get_cache_tile_key(cache_location, tile)
    await redis.delete(*build_evicted_keys())


async def invalidate_full_layer_cache(redis, layer: Layer, version: str):
    """
    Invalidate cache for a whole layer

    Args:
        layer_slug (str): The layer for which the cache has to be invalidated.
    """
    layer_prefix = get_layer_cache_prefix(layer, version)
    key_pattern = f"{layer_prefix}.*"

    delete_args = await redis.keys(key_pattern)
    await redis.delete(*delete_args)
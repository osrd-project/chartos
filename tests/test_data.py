import pyproj
from shapely.geometry import shape
from shapely.ops import transform


pseudo_mercator = pyproj.CRS('EPSG:3857')
gps = pyproj.CRS('EPSG:4326')
gps_to_pseudo_mercator = pyproj.Transformer.from_crs(
    gps, pseudo_mercator, always_xy=True).transform


campus_sncf_gps = shape({
    "type": "Point",
    "coordinates": [
        2.3538637161254883,
        48.9210857797314
    ]
})

campus_sncf_mercator = transform(
    gps_to_pseudo_mercator,
    campus_sncf_gps
)

ref_tiles = {
    (132786, 90113, 18),
    (66393, 45056, 17),
    (33196, 22528, 16),
    (16598, 11264, 15),
    (8299, 5632, 14),
    (4149, 2816, 13),
    (2074, 1408, 12),
    (1037, 704, 11),
    (518, 352, 10),
    (259, 176, 9),
    (129, 88, 8),
    (64, 44, 7),
    (32, 22, 6),
    (16, 11, 5),
    (8, 5, 4),
    (4, 2, 3),
    (2, 1, 2),
    (1, 0, 1),
    (0, 0, 0),
}

import math


def tile_to_latlng(x, y, z):
    """ Return the lat/lng of a map tile

    @param x: X coordinate of the tile
    @param y: Y coordinate of the tile
    @param z: Z coordinate of the tile
    @return: A tuple (lat,lng) of the corresponding top left corner of the tile
    """
    n = 2 ** z
    lng_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lng_deg


def tile_to_latlng_bbox(x, y, z):
    """Return the bounding box (in lat/lng) of a map tile

    @param x:  X coordinate of the tile
    @param y:  Y coordintate of the tile
    @param z:  Z coordinate of the tile
    @return: ((lat_min,lng_min),(lat_max,lng_max))
    """
    top_left = tile_to_latlng(x, y, z)
    bottom_right = tile_to_latlng(x+1, y+1, z)
    return top_left, bottom_right
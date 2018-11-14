# Versioned datastore maps

A CKAN plugin with a map view for versioned-datastore backed resources allowing for map visualizations of large resources with millions of data points.

To use this extension you must be install:

- [ckanext-versioned-datastore extension](https://github.com/NaturalHistoryMuseum/ckanext-versioned-datastore)
- [versioned-datastore-tile-server](https://github.com/NaturalHistoryMuseum/versioned-datastore-tile-server)

See those repositories for installing information.

This repository is a fork* of [ckanext-map](https://github.com/NaturalHistoryMuseum/ckanext-map).

_*you can't fork repositories within the same organisation so this repository is a duplicate of ckanext-map_

## Configuration
The plugin supports the following configuration options:

| Name | Description | Default |
|------|-------------|---------|
| `versioned_tilemap.tile_layer.url` | The URL to use for the base world tiles | `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` |
| `versioned_tilemap.tile_layer.opacity` | The opacity for the tile layer | `0.8` |
| `versioned_tilemap.zoom_bounds.min` | Minimum zoom level for initial display of the resource's data | `3` |
| `versioned_tilemap.zoom_bounds.max` | Maximum zoom level for initial display of the resource's data | `18` |
| `versioned_tilemap.style.plot.point_radius` | The integer radius of the rendered points (including the border) | `4` |
| `versioned_tilemap.style.plot.point_colour` | The hex value to render the points in | `#ee0000` ![#ee0000](https://placehold.it/15/ee0000/000000?text=+) |
| `versioned_tilemap.style.plot.border_width` | The integer border width of the rendered points | `1` |
| `versioned_tilemap.style.plot.border_colour` | The hex value to render the borders of the points in | `#ffffff` ![#ffffff](https://placehold.it/15/ffffff/000000?text=+) |
| `versioned_tilemap.style.plot.grid_resolution` | The integer size of the cells in the grid that each tile is split into for the UTFGrid. The default of `4` produces a 64x64 grid within each tile | `4` |
| `versioned_tilemap.style.gridded.cold_colour` |  The hex value to be used to render the points with the lowest counts | `#f4f11a` ![#f4f11a](https://placehold.it/15/f4f11a/000000?text=+) |
| `versioned_tilemap.style.gridded.hot_colour` |  The hex value to be used to render the points with the highest counts | `#f02323` ![#f02323](https://placehold.it/15/f02323/000000?text=+) |
| `versioned_tilemap.style.gridded.range_size` |  This many colours will be used to render the points dependant on their counts | `12` |
| `versioned_tilemap.style.gridded.resize_factor` | A resize value to use when smoothing the tile. This value will be used to scale the tile and then down (with anti-aliasing) to produce a smoother output. Increasing this value will negatively impact performance | `4` |
| `versioned_tilemap.style.gridded.grid_resolution` | The integer size of the cells in the grid that each tile is split into. The default of `8` produces a 32x32 grid within each tile and therefore matches the default `grid.json` setting too | `8` |
| `versioned_tilemap.style.heatmap.point_radius` | The integer radius of the rendered points (including the border) | `8` |
| `versioned_tilemap.style.heatmap.cold_colour` |  The hex value to be used to render the points with the lowest counts | `#0000ee` ![#0000ee](https://placehold.it/15/0000ee/000000?text=+) |
| `versioned_tilemap.style.heatmap.hot_colour` |  The hex value to be used to render the points with the highest counts | `#ee0000` ![#ee0000](https://placehold.it/15/ee0000/000000?text=+) |
| `versioned_tilemap.style.heatmap.intensity` | The decimal intensity (between 0 and 1) to render the tile with | `0.5` |
| `versioned_tilemap.info_template` | The name of the template to use when a point is clicked | `point_detail` |
| `versioned_tilemap.quick_info_template` | The name of the template to use when a point is hovered over | `point_detail_hover` |

## Usage
Once the plugin has been enabled (added to the list of plugins in the .ini file), users can add tiled map views from the resource management page.
The view will only be available to the user if they have selected a latitude and longitude field for the resource, this can be done on the edit resource page.

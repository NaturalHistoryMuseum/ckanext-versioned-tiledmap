<img src=".github/nhm-logo.svg" align="left" width="150px" height="100px" hspace="40"/>

# ckanext-versioned-tiledmap

[![Travis](https://img.shields.io/travis/NaturalHistoryMuseum/ckanext-versioned-tiledmap/master.svg?style=flat-square)](https://travis-ci.org/NaturalHistoryMuseum/ckanext-versioned-tiledmap)
[![Coveralls](https://img.shields.io/coveralls/github/NaturalHistoryMuseum/ckanext-versioned-tiledmap/master.svg?style=flat-square)](https://coveralls.io/github/NaturalHistoryMuseum/ckanext-versioned-tiledmap)
[![CKAN](https://img.shields.io/badge/ckan-2.9.0a-orange.svg?style=flat-square)](https://github.com/ckan/ckan)

_A CKAN extension with a map view for versioned-datastore backed resources._


# Overview

A CKAN plugin with a map view for versioned-datastore backed resources allowing for map visualizations of large resources with millions of data points.

This repository is a fork* of [ckanext-map](https://github.com/NaturalHistoryMuseum/ckanext-map).

_*you can't fork repositories within the same organisation, so this repository is a duplicate of ckanext-map._


# Installation

0. This extension depends on these projects, which must be installed first:
    - [ckanext-versioned-datastore extension](https://github.com/NaturalHistoryMuseum/ckanext-versioned-datastore)
    - [versioned-datastore-tile-server](https://github.com/NaturalHistoryMuseum/versioned-datastore-tile-server)

Path variables used below:
- `$INSTALL_FOLDER` (i.e. where CKAN is installed), e.g. `/usr/lib/ckan/default`
- `$CONFIG_FILE`, e.g. `/etc/ckan/default/development.ini`

1. Clone the repository into the `src` folder:

  ```bash
  cd $INSTALL_FOLDER/src
  git clone https://github.com/NaturalHistoryMuseum/ckanext-versioned-tiledmap.git
  ```

2. Activate the virtual env:

  ```bash
  . $INSTALL_FOLDER/bin/activate
  ```

3. Install the requirements from requirements.txt:

  ```bash
  cd $INSTALL_FOLDER/src/ckanext-versioned-tiledmap
  pip install -r requirements.txt
  ```

4. Run setup.py:

  ```bash
  cd $INSTALL_FOLDER/src/ckanext-versioned-tiledmap
  python setup.py develop
  ```

5. Add 'versioned-tiledmap' to the list of plugins in your `$CONFIG_FILE`:

  ```ini
  ckan.plugins = ... versioned-tiledmap
  ```

# Configuration

These are the options that can be specified in your .ini config file.

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


# Further Setup

Add latitude and longitude values for the resources you want to use this view for.


# Usage

After enabling this extension in the list of plugins, the Map view should become available for resources with latitude and longitude values.


# Testing

_Test coverage is currently extremely limited._

To run the tests, use nosetests inside your virtualenv. The `--nocapture` flag will allow you to see the debug statements.
```bash
nosetests --ckan --with-pylons=$TEST_CONFIG_FILE --where=$INSTALL_FOLDER/src/ckanext-versioned-tiledmap --nologcapture --nocapture
```

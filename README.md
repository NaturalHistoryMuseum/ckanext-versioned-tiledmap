<!--header-start-->
<img src=".github/nhm-logo.svg" align="left" width="150px" height="100px" hspace="40"/>

# ckanext-versioned-tiledmap

[![Tests](https://img.shields.io/github/workflow/status/NaturalHistoryMuseum/ckanext-versioned-tiledmap/Tests?style=flat-square)](https://github.com/NaturalHistoryMuseum/ckanext-versioned-tiledmap/actions/workflows/main.yml)
[![Coveralls](https://img.shields.io/coveralls/github/NaturalHistoryMuseum/ckanext-versioned-tiledmap/main?style=flat-square)](https://coveralls.io/github/NaturalHistoryMuseum/ckanext-versioned-tiledmap)
[![CKAN](https://img.shields.io/badge/ckan-2.9.1-orange.svg?style=flat-square)](https://github.com/ckan/ckan)
[![Python](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-blue.svg?style=flat-square)](https://www.python.org/)
[![Docs](https://img.shields.io/readthedocs/ckanext-versioned-tiledmap?style=flat-square)](https://ckanext-versioned-tiledmap.readthedocs.io)

_A CKAN extension with a map view for versioned-datastore backed resources._

<!--header-end-->

# Overview

<!--overview-start-->
A CKAN plugin with a map view for versioned-datastore backed resources allowing for map visualizations of large resources with millions of data points.

This repository is a fork* of [ckanext-map](https://github.com/NaturalHistoryMuseum/ckanext-map).

_*you can't fork repositories within the same organisation, so this repository is a duplicate of ckanext-map._

<!--overview-end-->

# Installation

<!--installation-start-->
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

5. Add 'versioned_tiledmap' to the list of plugins in your `$CONFIG_FILE`:

  ```ini
  ckan.plugins = ... versioned_tiledmap
  ```

6. Add latitude and longitude values for the resources you want to use this view for.

<!--installation-end-->

# Configuration

<!--configuration-start-->
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

<!--configuration-end-->

# Usage

<!--usage-start-->
After enabling this extension in the list of plugins, the Map view should become available for resources with latitude and longitude values.

<!--usage-end-->

# Testing

<!--testing-start-->
There is a Docker compose configuration available in this repository to make it easier to run tests.

To run the tests against ckan 2.9.x on Python3:

1. Build the required images
```bash
docker-compose build
```

2. Then run the tests.
   The root of the repository is mounted into the ckan container as a volume by the Docker compose
   configuration, so you should only need to rebuild the ckan image if you change the extension's
   dependencies.
```bash
docker-compose run ckan
```

The ckan image uses the Dockerfile in the `docker/` folder.

<!--testing-end-->

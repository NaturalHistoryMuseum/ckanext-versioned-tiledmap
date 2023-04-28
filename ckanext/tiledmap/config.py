#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of a project
# Created by the Natural History Museum in London, UK

# default configuration
config = {
    # we don't want to let users define this per dataset, as we need to ensure we have the right to
    # use the tiles
    'versioned_tilemap.tile_layer.url': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    'versioned_tilemap.tile_layer.attribution': 'Base tiles provided by OpenStreetMap. <a href="openstreetmap.org/copyright">View copyright information</a>',
    'versioned_tilemap.tile_layer.opacity': 0.8,
    # max/min zoom constraints
    'versioned_tilemap.zoom_bounds.min': 3,
    'versioned_tilemap.zoom_bounds.max': 18,
    # the tiled map autozooms to the dataset's features. The autozoom can be constrained here if we
    # want to avoid too little or too much context
    'versioned_tilemap.initial_zoom.min': 3,
    'versioned_tilemap.initial_zoom.max': 18,
    # the default style parameters for the plot map
    'versioned_tilemap.style.plot.point_radius': 4,
    'versioned_tilemap.style.plot.point_colour': '#ee0000',
    'versioned_tilemap.style.plot.border_width': 1,
    'versioned_tilemap.style.plot.border_colour': '#ffffff',
    'versioned_tilemap.style.plot.grid_resolution': 4,
    # the default style parameters for the grid map
    'versioned_tilemap.style.gridded.grid_resolution': 8,
    'versioned_tilemap.style.gridded.cold_colour': '#f4f11a',
    'versioned_tilemap.style.gridded.hot_colour': '#f02323',
    'versioned_tilemap.style.gridded.range_size': 12,
    # the style parameters for the heatmap
    'versioned_tilemap.style.heatmap.point_radius': 8,
    'versioned_tilemap.style.heatmap.cold_colour': '#0000ee',
    'versioned_tilemap.style.heatmap.hot_colour': '#ee0000',
    'versioned_tilemap.style.heatmap.intensity': 0.5,
    # templates used for hover and click information on the map
    'versioned_tilemap.info_template': 'point_detail',
    'versioned_tilemap.quick_info_template': 'point_detail_hover',
}

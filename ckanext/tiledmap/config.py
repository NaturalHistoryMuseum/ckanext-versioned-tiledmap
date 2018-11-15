#!/usr/bin/env python
# encoding: utf-8

# default configuration
config = {
    # we don't want to let users define this per dataset, as we need to ensure we have the right to
    # use the tiles
    u'versioned_tilemap.tile_layer.url': u'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    u'versioned_tilemap.tile_layer.opacity': 0.8,

    # max/min zoom constraints
    u'versioned_tilemap.zoom_bounds.min': 3,
    u'versioned_tilemap.zoom_bounds.max': 18,

    # the tiled map autozooms to the dataset's features. The autozoom can be constrained here if we
    # want to avoid too little or too much context
    u'versioned_tilemap.initial_zoom.min': 3,
    u'versioned_tilemap.initial_zoom.max': 18,

    # the default style parameters for the plot map
    u'versioned_tilemap.style.plot.point_radius': 4,
    u'versioned_tilemap.style.plot.point_colour': u'#ee0000',
    u'versioned_tilemap.style.plot.border_width': 1,
    u'versioned_tilemap.style.plot.border_colour': u'#ffffff',
    u'versioned_tilemap.style.plot.grid_resolution': 4,

    # the default style parameters for the grid map
    u'versioned_tilemap.style.gridded.grid_resolution': 8,
    u'versioned_tilemap.style.gridded.cold_colour': u'#f4f11a',
    u'versioned_tilemap.style.gridded.hot_colour': u'#f02323',
    u'versioned_tilemap.style.gridded.range_size': 12,

    # the style parameters for the heatmap
    u'versioned_tilemap.style.heatmap.point_radius': 8,
    u'versioned_tilemap.style.heatmap.cold_colour': u'#0000ee',
    u'versioned_tilemap.style.heatmap.hot_colour': u'#ee0000',
    u'versioned_tilemap.style.heatmap.intensity': 0.5,

    # templates used for hover and click information on the map
    u'versioned_tilemap.info_template': u'point_detail',
    u'versioned_tilemap.quick_info_template': u'point_detail_hover',
}

# Default configuration
config = {
    # Information about the base layer used for the maps.
    # We don't want to let users define this per dataset, as we need to ensure we have the right to use the tiles.
    'tiledmap.tile_layer.url': 'http://{s}.tiles.mapbox.com/v4/mapbox.streets/{z}/{x}/{y}@2x.png?access_token=pk.eyJ1IjoibmhtIiwiYSI6ImNpcjU5a3VuNDAwMDNpYm5vY251MW5oNTIifQ.JuGQ2xZ66FKOAOhYl2HdWQ',
    'tiledmap.tile_layer.opacity': '0.8',

    # Max/min zoom constraints
    'tiledmap.zoom_bounds.min': '3',
    'tiledmap.zoom_bounds.max': '18',

    # The tiled map autozooms to the dataset's features. The autozoom can be constrained here to avoid too little or
    # too much context.
    # TODO: Configure this per dataset?
    'tiledmap.initial_zoom.min': '3',
    'tiledmap.initial_zoom.max': '6',

    # The style parameters for the plot map. The colors can be defined per dataset (with the defaults provided in the
    # main config if present, or here otherwise), but the marker size and resolution can only be set in the main
    # config (if present, or here otherwise) as they have a notable performance impact on larger datasets.
    'tiledmap.style.plot.fill_color': '#EE0000',
    'tiledmap.style.plot.line_color': '#FFFFFF',
    'tiledmap.style.plot.marker_size': '8',
    'tiledmap.style.plot.grid_resolution': '4',

    # The style parameters for the grid map. The base color can be defined per dataset (with the defaults provided in
    # the main config if present, or here otherwise), but the marker size and grid resolution can only be set in the
    # main config (if present, or here otherwise) as they have a notable performance impact on larger datasets.
    'tiledmap.style.gridded.base_color': '#F02323',
    'tiledmap.style.gridded.marker_size': '8',
    'tiledmap.style.gridded.grid_resolution': '8',

    # The style parameters for the heatmap. The intensity can be defined per dataset (with the default provided in
    # the main config if present, or here otherwise), but the marker url and marker size can only be set in the main
    # config (if present, or here otherwise) as they have a notable performance impact on larger datasets.
    'tiledmap.style.heatmap.intensity': '0.1',
    'tiledmap.style.heatmap.gradient': '#0000FF, #00FFFF, #00FF00, #FFFF00, #FFA500, #FF0000',
    'tiledmap.style.heatmap.marker_url': '!markers!/alpharadiantdeg20px.png',
    'tiledmap.style.heatmap.marker_size': '20',

    # Templates used for hover and click information on the map.
    'tiledmap.info_template': 'point_detail',
    'tiledmap.quick_info_template': 'point_detail_hover'
}
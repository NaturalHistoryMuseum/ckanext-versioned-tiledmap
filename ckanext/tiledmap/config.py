# Default configuration
config = {
    # Unique id field on the datastore table containing the geometric data. By default this is _id,
    # and you should only change this if you know what you are doing. For performance reasons it is
    # important that there is a unique index on that column.
    'tiledmap.unique_id_field': '_id',

    # The named of the fields that are inserted into the datastore table to hold the geom data. Note
    # that fields that start with an underscore are considered hidden by the datastore. Also note that
    # if you change those after some map views were created, those map views won't work anymore and will need manual
    # fix.
    'tiledmap.geom_field': '_the_geom_webmercator',
    'tiledmap.geom_field_4326': '_geom',

    # Information about the base layer used for the maps.
    # We don't want to let users define this per dataset, as we need to ensure we have the right to use the tiles.
    'tiledmap.tile_layer.url': 'http://otile1.mqcdn.com/tiles/1.0.0/map/{z}/{x}/{y}.jpg',
    'tiledmap.tile_layer.opacity': '0.8',

    # The tiled map autozooms to the dataset's features. The autozoom can be constrained here to avoid too little or
    # too much context.
    # TODO: Configure this per dataset?
    'tiledmap.initial_zoom.min': '2',
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
# Default configuration
config = {
    # The named of the fields that are inserted into the datastore table to hold the geom data. Note
    # that fields that start with an underscore are considered hidden by the datastore. Also note that
    # if you change those after some map views were created, those map views won't work anymore and will need manual
    # fix.
    'tiledmap.geom_field': '_the_geom_webmercator',
    'tiledmap.geom_field_4326': '_geom',

    # Information about the base layer used for the maps.
    # TODO: Configure this per dataset?
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
    # TODO: Whether the map can be hovered/clicked, the type of template, and the fields to use should be configured per dataset.
    'tiledmap.info_template': 'point_detail.dwc.mustache',
    'tiledmap.title_template': 'point_detail_title.dwc.mustache',
    'tiledmap.quick_info_template': 'point_detail_hover.dwc.mustache',
    'tiledmap.info_fields': 'Record:_id,Scientific Name:scientificName,Kingdom:kingdom,Phylum:phylum,Class:class,Order:order,Family:family,Genus:genus,Subgenus:subgenus,Institution Code:institutionCode,Catalogue Number:catalogNumber,Collection Code:collectionCode,Identified By:identifiedBy,Date:dateIdentified,Continent:continent,Country:country,State/Province:stateProvince,County:county,Locality:locality,Habitat:habitat'
}
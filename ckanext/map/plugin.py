import ckan.plugins as p

import ckan.logic as logic
get_action = logic.get_action


class MapPlugin(p.SingletonPlugin):
    """Windshaft map plugin

    This plugin replaces the recline preview template to use a custom map engine.
    The plugin provides controller routes to server tiles and grid from the winsdhaft
    backend. See MapController for configuration options.
    """
    p.implements(p.IConfigurer)
    p.implements(p.IRoutes, inherit=True)

    ## IConfigurer
    def update_config(self, config):
        p.toolkit.add_template_directory(config, 'theme/templates')
        p.toolkit.add_public_directory(config, 'theme/public')
        p.toolkit.add_resource('theme/public', 'map')


    ## IRoutes
    def before_map(self, map):

        # Add map controller
        map.connect('/map-tile/{z}/{x}/{y}.png', controller='ckanext.map.controllers.map:MapController', action='tile')
        map.connect('/map-grid/{z}/{x}/{y}.grid.json', controller='ckanext.map.controllers.map:MapController', action='grid')
        map.connect('/map-info', controller='ckanext.map.controllers.map:MapController', action='map_info')

        return map
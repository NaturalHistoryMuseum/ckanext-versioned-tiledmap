import ckan.plugins as p
import ckanext.map.logic.action as map_action
import ckanext.map.logic.auth as map_auth

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
    p.implements(p.IActions)
    p.implements(p.IAuthFunctions)

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

    ## IActions
    def get_actions(self):
        return {
            'create_geom_columns': map_action.create_geom_columns,
            'update_geom_columns': map_action.update_geom_columns
        }

    ## IAuthFunctions
    def get_auth_functions(self):
        return {
            'create_geom_columns': map_auth.create_geom_columns,
            'update_geom_columns': map_auth.update_geom_columns
        }
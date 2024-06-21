#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of a project
# Created by the Natural History Museum in London, UK

from ckan.common import json
from ckan.plugins import toolkit, implements, interfaces, SingletonPlugin

from ckanext.tiledmap import routes
from ckanext.tiledmap.config import config as plugin_config
from ckanext.tiledmap.lib import validators
from ckanext.tiledmap.lib.helpers import mustache_wrapper, dwc_field_title
from ckanext.tiledmap.lib.utils import get_resource_datastore_fields
import urllib.request

try:
    from ckanext.status.interfaces import IStatus

    status_available = True
except ImportError:
    status_available = False

boolean_validator = toolkit.get_validator('boolean_validator')
ignore_empty = toolkit.get_validator('ignore_empty')


class VersionedTiledMapPlugin(SingletonPlugin):
    """
    Map plugin which uses the versioned-datastore-tile-server to render a map of the
    data in a resource.
    """

    implements(interfaces.IConfigurer)
    implements(interfaces.IBlueprint, inherit=True)
    implements(interfaces.ITemplateHelpers)
    implements(interfaces.IResourceView, inherit=True)
    implements(interfaces.IConfigurable)
    if status_available:
        implements(IStatus)

    # from IConfigurer interface
    def update_config(self, config):
        """
        Add our various resources and template directories to the list of available
        ones.
        """
        toolkit.add_template_directory(config, 'theme/templates')
        toolkit.add_public_directory(config, 'theme/public')
        toolkit.add_resource('theme/assets', 'tiledmap')

    ## IBlueprint
    def get_blueprint(self):
        return routes.blueprints

    # from ITemplateHelpers interface
    def get_helpers(self):
        """
        Add a template helper for formatting mustache templates server side.
        """
        return {'mustache': mustache_wrapper, 'dwc_field_title': dwc_field_title}

    # from IConfigurable interface
    def configure(self, config):
        plugin_config.update(config)

    # from IResourceView interface
    def info(self):
        """
        Return generic info about the plugin.
        """
        return {
            'name': 'versioned_tiledmap',
            'title': 'Map',
            'schema': {
                # plot settings
                'enable_plot_map': [ignore_empty, boolean_validator],
                'plot_point_radius': [ignore_empty, int],
                'plot_point_colour': [ignore_empty, validators.colour_validator],
                'plot_border_width': [ignore_empty, int],
                'plot_border_colour': [ignore_empty, validators.colour_validator],
                # gridded settings
                'enable_grid_map': [ignore_empty, boolean_validator],
                'gridded_grid_resolution': [ignore_empty, int],
                'gridded_cold_colour': [ignore_empty, validators.colour_validator],
                'gridded_hot_colour': [ignore_empty, validators.colour_validator],
                'gridded_range_size': [ignore_empty, int],
                # heatmap settings
                'enable_heat_map': [ignore_empty, boolean_validator],
                'heatmap_point_radius': [ignore_empty, int],
                'heatmap_cold_colour': [ignore_empty, validators.colour_validator],
                'heatmap_hot_colour': [ignore_empty, validators.colour_validator],
                'heatmap_intensity': [ignore_empty, validators.float_01_validator],
                # utfgrid settings
                'enable_utf_grid': [ignore_empty, boolean_validator],
                'utf_grid_title': [ignore_empty, validators.is_datastore_field],
                'utf_grid_fields': [ignore_empty, validators.is_datastore_field],
                # other settings
                'repeat_map': [ignore_empty, boolean_validator],
                'overlapping_records_view': [ignore_empty, validators.is_view_id],
                '__extras': [ignore_empty],
            },
            'icon': 'compass',
            'iframed': True,
            'filterable': True,
            'preview_enabled': False,
            'full_page_edit': False,
        }

    # from IResourceView interface
    def view_template(self, context, data_dict):
        return 'map_view.html'

    # from IResourceView interface
    def form_template(self, context, data_dict):
        return 'map_form.html'

    # from IResourceView interface
    def can_view(self, data_dict):
        """
        Only datastore resources can use this view and they have to have both latitude
        and longitude field names set.
        """
        required_fields = ['datastore_active', '_latitude_field', '_longitude_field']
        return all(data_dict['resource'].get(field, False) for field in required_fields)

    # from IResourceView interface
    def setup_template_variables(self, context, data_dict):
        """
        Setup variables available to templates.
        """
        # TODO: Apply variables to appropriate view
        resource = data_dict['resource']
        resource_view = data_dict['resource_view']
        resource_view_id = resource_view.get('id', None)
        # get the names of the fields on this resource in the datastore
        fields = get_resource_datastore_fields(resource['id'])
        # find all the views on this resource currently
        views = toolkit.get_action('resource_view_list')(
            context, {'id': resource['id']}
        )

        # build a list of view options, adding a default view option of no view first
        view_options = [{'text': toolkit._('(None)'), 'value': ''}]
        # then loop through and add the other views
        for view in views:
            # but make sure we don't add this view to the list of options
            if resource_view_id == view['id']:
                continue
            view_options.append({'text': view['title'], 'value': view['id']})

        return {
            'resource_json': json.dumps(resource),
            'resource_view_json': json.dumps(resource_view),
            'map_fields': [{'text': field, 'value': field} for field in fields],
            'available_views': view_options,
            'defaults': plugin_config,
            'is_new': resource_view_id is None,
        }

    ## IStatus
    def modify_status_reports(self, status_reports):
        tileserver_url = toolkit.config.get('versioned_tilemap.tile_server')

        tileserver_text = toolkit._('unknown')
        tileserver_state = 'neutral'

        if tileserver_url:
            try:
                with urllib.request.urlopen(tileserver_url + '/status') as response:
                    tileserver_response = response.read().decode()
            except Exception as e:
                tileserver_response = ''
            if tileserver_response == 'OK':
                tileserver_text = toolkit._('available')
                tileserver_state = 'good'
            else:
                tileserver_text = toolkit._('unavailable')
                tileserver_state = 'bad'

        status_reports.append(
            {
                'label': toolkit._('Maps'),
                'value': tileserver_text,
                'help': toolkit._(
                    'Connection to the server that plots data points on maps'
                ),
                'state': tileserver_state,
            }
        )

        return status_reports

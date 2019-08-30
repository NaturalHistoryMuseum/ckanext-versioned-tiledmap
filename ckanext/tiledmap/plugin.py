#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of a project
# Created by the Natural History Museum in London, UK

from ckan.common import json
from ckan.plugins import toolkit, implements, interfaces, SingletonPlugin
from ckanext.tiledmap.config import config as plugin_config
from ckanext.tiledmap.lib import validators
from ckanext.tiledmap.lib.helpers import mustache_wrapper, dwc_field_title
from ckanext.tiledmap.lib.utils import get_resource_datastore_fields
from ckanext.tiledmap import routes

boolean_validator = toolkit.get_validator(u'boolean_validator')
ignore_empty = toolkit.get_validator(u'ignore_empty')


class VersionedTiledMapPlugin(SingletonPlugin):
    '''
    Map plugin which uses the versioned-datastore-tile-server to render a map of the data in a
    resource.
    '''
    implements(interfaces.IConfigurer)
    implements(interfaces.IBlueprint, inherit=True)
    implements(interfaces.ITemplateHelpers)
    implements(interfaces.IResourceView, inherit=True)
    implements(interfaces.IConfigurable)

    # from IConfigurer interface
    def update_config(self, config):
        '''
        Add our various resources and template directories to the list of available ones.
        '''
        toolkit.add_template_directory(config, u'theme/templates')
        toolkit.add_public_directory(config, u'theme/public')
        toolkit.add_resource(u'theme/public', u'tiledmap')

    ## IBlueprint
    def get_blueprint(self):
        return routes.blueprints

    # from ITemplateHelpers interface
    def get_helpers(self):
        '''Add a template helper for formating mustache templates server side'''
        return {
            u'mustache': mustache_wrapper,
            u'dwc_field_title': dwc_field_title
        }

    # from IConfigurable interface
    def configure(self, config):
        plugin_config.update(config)

    # from IResourceView interface
    def info(self):
        '''
        Return generic info about the plugin.
        '''
        return {
            u'name': u'versioned_tiledmap',
            u'title': u'Map',
            u'schema': {
                # plot settings
                u'enable_plot_map': [ignore_empty, boolean_validator],
                u'plot_point_radius': [ignore_empty, int],
                u'plot_point_colour': [ignore_empty, validators.colour_validator],
                u'plot_border_width': [ignore_empty, int],
                u'plot_border_colour': [ignore_empty, validators.colour_validator],
                # gridded settings
                u'enable_grid_map': [ignore_empty, boolean_validator],
                u'gridded_grid_resolution': [ignore_empty, int],
                u'gridded_cold_colour': [ignore_empty, validators.colour_validator],
                u'gridded_hot_colour': [ignore_empty, validators.colour_validator],
                u'gridded_range_size': [ignore_empty, int],
                # heatmap settings
                u'enable_heat_map': [ignore_empty, boolean_validator],
                u'heatmap_point_radius': [ignore_empty, int],
                u'heatmap_cold_colour': [ignore_empty, validators.colour_validator],
                u'heatmap_hot_colour': [ignore_empty, validators.colour_validator],
                u'heatmap_intensity': [ignore_empty, validators.float_01_validator],
                # utfgrid settings
                u'enable_utf_grid': [ignore_empty, boolean_validator],
                u'utf_grid_title': [ignore_empty, validators.is_datastore_field],
                u'utf_grid_fields': [ignore_empty, validators.is_datastore_field],
                # other settings
                u'repeat_map': [ignore_empty, boolean_validator],
                u'overlapping_records_view': [ignore_empty, validators.is_view_id],
                u'__extras': [ignore_empty]
            },
            u'icon': u'compass',
            u'iframed': True,
            u'filterable': True,
            u'preview_enabled': False,
            u'full_page_edit': False
        }

    # from IResourceView interface
    def view_template(self, context, data_dict):
        return u'map_view.html'

    # from IResourceView interface
    def form_template(self, context, data_dict):
        return u'map_form.html'

    # from IResourceView interface
    def can_view(self, data_dict):
        '''
        Only datastore resources can use this view and they have to have both latitude and longitude
        field names set.
        '''
        required_fields = [u'datastore_active', u'_latitude_field', u'_longitude_field']
        return all(data_dict[u'resource'].get(field, False) for field in required_fields)

    # from IResourceView interface
    def setup_template_variables(self, context, data_dict):
        '''
        Setup variables available to templates.
        '''
        # TODO: Apply variables to appropriate view
        resource = data_dict[u'resource']
        resource_view = data_dict[u'resource_view']
        resource_view_id = resource_view.get(u'id', None)
        # get the names of the fields on this resource in the datastore
        fields = get_resource_datastore_fields(resource[u'id'])
        # find all the views on this resource currently
        views = toolkit.get_action(u'resource_view_list')(context, {u'id': resource[u'id']})

        # build a list of view options, adding a default view option of no view first
        view_options = [{u'text': toolkit._(u'(None)'), u'value': u''}]
        # then loop through and add the other views
        for view in views:
            # but make sure we don't add this view to the list of options
            if resource_view_id == view[u'id']:
                continue
            view_options.append({u'text': view[u'title'], u'value': view[u'id']})

        return {
            u'resource_json': json.dumps(resource),
            u'resource_view_json': json.dumps(resource_view),
            u'map_fields': [{u'text': field, u'value': field} for field in fields],
            u'available_views': view_options,
            u'defaults': plugin_config,
            u'is_new': resource_view_id is None,
        }

import re
import json
import urllib
import urlparse

from pylons import config
import paste.fixture
from sqlalchemy import create_engine
import nose
from mock import patch

import ckan
import ckan.tests as tests
import ckan.plugins as p
import ckan.config.middleware as middleware
import ckan.lib.create_test_data as ctd
from ckan.logic.action.create import package_create
from ckan.logic.action.delete import package_delete
from ckanext.datastore.logic.action import datastore_create, datastore_delete, datastore_upsert
from ckanext.tiledmap.config import config as tm_config

from nose.tools import assert_equal, assert_true, assert_false, assert_in

class TestTileFetching(tests.WsgiAppCase):
    """Test cases for the Map plugin"""
    dataset = None
    resource = None
    context = None

    @classmethod
    @patch('ckan.lib.helpers.flash')
    def setup_class(cls, mock_flash):
        """Prepare the test"""
        # We need datastore for these tests.
        if not tests.is_datastore_supported():
            raise nose.SkipTest("Datastore not supported")

        # Setup a test app
        wsgiapp = middleware.make_app(config['global_conf'], **config)
        cls.app = paste.fixture.TestApp(wsgiapp)
        ctd.CreateTestData.create()
        cls.context = {'model': ckan.model,
                       'session': ckan.model.Session,
                       'user': ckan.model.User.get('testsysadmin').name}

        # Load plugins
        p.load('tiledmap')
        p.load('datastore')

        # Set windshaft host/port as these settings do not have a default.
        # TODO: Test that calls fail if not set
        tm_config.update({
            'tiledmap.windshaft.host': '127.0.0.1',
            'tiledmap.windshaft.port': '4000'
        })

        # Copy tiledmap settings
        cls.config = dict(tm_config.items())

        # Setup a dummy datastore.
        cls.dataset = package_create(cls.context, {'name': 'map-test-dataset'})
        cls.resource = datastore_create(cls.context, {
            'resource': {
                'package_id': cls.dataset['id']
            },
            'fields': [
                {'id': 'id', 'type': 'integer'},
                {'id': 'latitude', 'type': 'numeric'},
                {'id': 'longitude', 'type': 'numeric'},
                {'id': 'some_field_1', 'type': 'text'},
                {'id': 'some_field_2', 'type': 'text'}
            ],
            'primary_key': 'id'
        })

        # Add some data. We add 4 records such that:
        # - The first three records have 'some_field_1' set to 'hello' ;
        # - The third record does not have a geom ;
        # - The fourth record has a geom, but 'some_field_1' is set to something elese.
        datastore_upsert(cls.context, {
            'resource_id': cls.resource['resource_id'],
            'method': 'upsert',
            'records': [{
                'id': '1',
                'latitude': -15,
                'longitude': -11,
                'some_field_1': 'hello',
                'some_field_2': 'world'
            }, {
                'id': 2,
                'latitude': 48,
                'longitude': 23,
                'some_field_1': 'hello',
                'some_field_2': 'again'
            }, {
                'id': 3,
                'latitude': None,
                'longitude': None,
                'some_field_1': 'hello',
                'some_field_2': 'hello'
            }, {
                'id': 4,
                'latitude': 80,
                'longitude': 80,
                'some_field_1': 'all your bases',
                'some_field_2': 'are belong to us'
            }]
        })

        # Create a tiledmap resource view. This process itself is fully tested in test_view_create.py.
        # This will also generate the geometry column - that part of the process is fully tested in test_actions
        data_dict = {
            'description': u'',
            'title': u'test',
            'resource_id': cls.resource['resource_id'],
            'plot_marker_color': u'#EE0000',
            'enable_plot_map': u'True',
            'overlapping_records_view': u'',
            'longitude_field': u'longitude',
            'heat_intensity': u'0.1',
            'view_type': u'tiledmap',
            'utf_grid_title': u'_id',
            'plot_marker_line_color': u'#FFFFFF',
            'latitude_field': u'latitude',
            'enable_utf_grid': u'True',
            'utf_grid_fields' : ['some_field_1', 'some_field_2'],
            'grid_base_color': u'#F02323',
            'enable_heat_map': u'True',
            'enable_grid_map': u'True'
        }

        resource_view_create = p.toolkit.get_action('resource_view_create')
        cls.resource_view = resource_view_create(cls.context, data_dict)

        # Create a resource that does not have spatial fields
        cls.non_spatial_resource = datastore_create(cls.context, {
            'resource': {
                'package_id': cls.dataset['id']
            },
            'fields': [
                {'id': 'id', 'type': 'integer'},
                {'id': 'some_field', 'type': 'text'}
            ],
            'primary_key': 'id'
        })



    @classmethod
    def teardown_class(cls):
        """Clean up after the test"""
        datastore_delete(cls.context, {'resource_id': cls.resource['resource_id']})
        package_delete(cls.context, {'id': cls.dataset['id']})
        p.unload('tiledmap')
        p.unload('datastore')

    def teardown(self):
        # Ensure all settings are reset to default.
        tm_config.update(TestTileFetching.config)

    def test_map_info(self):
        """Test the map-info controller returns the expected data"""
        filters = 'some_field_1:hello'
        res = self.app.get('/map-info?resource_id={resource_id}&view_id={view_id}&filters={filters}&fetch_id={fetch_id}'.format(
            resource_id=TestTileFetching.resource['resource_id'],
            view_id=TestTileFetching.resource_view['id'],
            filters=urllib.quote_plus(filters),
            fetch_id=44
        ))
        values = json.loads(res.body)
        assert_true(values['geospatial'])
        assert_equal(values['geom_count'], 2)
        assert_equal(values['fetch_id'], '44')
        assert_in('initial_zoom', values)
        assert_in('tile_layer', values)
        assert_equal(values['bounds'], [[-15, -11], [48, 23]])
        assert_in('map_style', values)
        assert_in('plot', values['map_styles'])
        assert_in('heatmap', values['map_styles'])
        assert_in('gridded', values['map_styles'])
        for control in ['drawShape', 'mapType']:
            assert_in(control, values['control_options'])
            assert_in('position', values['control_options'][control])
        for plugin in ['tooltipInfo', 'pointInfo']:
            assert_in(plugin, values['plugin_options'])
        assert_in('template', values['plugin_options']['pointInfo'])
        assert_in('template', values['plugin_options']['tooltipInfo'])

from pylons import config
import paste.fixture
import nose
from sqlalchemy import create_engine
from sqlalchemy.sql import select
from sqlalchemy import Table, MetaData, func

import ckan
import ckan.tests as tests
import ckan.plugins as p
import ckan.plugins.toolkit as toolkit
import ckan.config.middleware as middleware
import ckan.lib.create_test_data as ctd
from ckan.logic import ValidationError
from ckan.logic.action.create import package_create
from ckan.logic.action.delete import package_delete
from ckanext.datastore.logic.action import datastore_create, datastore_delete, datastore_upsert

from nose.tools import assert_equal, assert_true, assert_false, assert_in, assert_raises
from mock import patch

class TestViewCreated(tests.WsgiAppCase):
    """These test cases check that tiled map views are created as expected, with appropriate default behaviour,
    and that the geometry columns are created as expected, with appropriate errore messages. Note that the actions
    that create the geometry columns are fully tested elsewhere.
    """""
    context = None
    engine = None

    @classmethod
    def setup_class(cls):
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
        cls.engine = create_engine(config['ckan.datastore.write_url'])

        # Load plugins
        p.load('tiledmap')
        p.load('datastore')

    @classmethod
    def teardown_class(cls):
        """Clean up"""
        p.unload('tiledmap')
        p.unload('datastore')

    def setup(self):
        """Prepare each test"""
        # Setup a dummy datastore.
        self.dataset = package_create(TestViewCreated.context, {'name': 'map-test-dataset'})
        self.resource = datastore_create(TestViewCreated.context, {
            'resource': {
                'package_id': self.dataset['id']
            },
            'fields': [
                {'id': 'id', 'type': 'integer'},
                {'id': 'latitude', 'type': 'double precision'},
                {'id': 'longitude', 'type': 'double precision'},
                {'id': 'long2', 'type': 'double precision'},
                {'id': 'text', 'type': 'text'},
                {'id': 'big', 'type': 'double precision'},
            ],
            'primary_key': 'id'
        })

        # Add some data.
        datastore_upsert(TestViewCreated.context, {
            'resource_id': self.resource['resource_id'],
            'method': 'upsert',
            'records': [{
                            'id': 1,
                            'latitude': -11,
                            'longitude': -15,
                            'long2': 22,
                            'text': 'hello',
                            'big': '-1000'
                        }, {
                            'id': 2,
                            'latitude': 23,
                            'longitude': 48,
                            'long2': -12,
                            'text': 'hello',
                            'big': '199'
                        }]
        })

        # Base dict for view creation/update methods
        self.base_data_dict = {
            'description': u'',
            'title': u'test',
            'resource_id': self.resource['resource_id'],
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
            'grid_base_color': u'#F02323'
        }

    def teardown(self):
        """Clean up after each test"""
        datastore_delete(TestViewCreated.context, {'resource_id': self.resource['resource_id']})
        package_delete(TestViewCreated.context, {'id': self.dataset['id']})

    @patch('ckan.lib.helpers.flash')
    def test_create_view_action_success(self, flash_mock):
        """Test the create view action directly. Ensure that all values validate when correct."""
        resource_view_create = toolkit.get_action('resource_view_create')
        data_dict = dict(self.base_data_dict.items())
        resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check we have lat/long values. This is done more extensively in test_actions.
        metadata = MetaData()
        table = Table(self.resource['resource_id'], metadata, autoload=True, autoload_with=TestViewCreated.engine)
        s = select([
            table.c['latitude'],
            table.c['longitude'],
            func.st_x(table.c['_geom']).label('x'),
            func.st_y(table.c['_geom']).label('y'),
        ]).where(table.c['_the_geom_webmercator'] != None)
        r = TestViewCreated.engine.execute(s)
        try:
            assert_equal(r.rowcount, 2)
            for row in r:
                assert_equal(float(row['x']), float(row['longitude']))
                assert_equal(float(row['y']), float(row['latitude']))
        except:
            raise
        finally:
            r.close()
        # Check we have a message to inform us all went well
        assert_true(flash_mock.called)
        assert_equal(flash_mock.call_args[1]['category'], 'alert-success')

    @patch('ckan.lib.helpers.flash')
    def test_create_view_action_failure(self, flash_mock):
        """Test the create view action directly (failure test)"""
        resource_view_create = toolkit.get_action('resource_view_create')
        # Check latitude must be numeric
        data_dict = dict(self.base_data_dict.items() + {'title' : 'test_la_n', 'latitude_field': 'text'}.items())
        with assert_raises(ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check latitude must be within range
        data_dict = dict(self.base_data_dict.items() + {'title' : 'test_la_r', 'latitude_field': 'big'}.items())
        with assert_raises(ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check longitude must be numeric
        data_dict = dict(self.base_data_dict.items() + {'title' : 'test_lo_n', 'longitude_field': 'text'}.items())
        with assert_raises(ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check longitude must be within range
        data_dict = dict(self.base_data_dict.items() + {'title' : 'test_lo_r', 'longitude_field': 'big'}.items())
        with assert_raises(ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check heat map intensity must be between 0 and 1
        data_dict = dict(self.base_data_dict.items() + {'title' : 'test_h', 'heat_intensity': '2'}.items())
        with assert_raises(ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check color validation
        data_dict = dict(self.base_data_dict.items() + {'title' : 'test_c', 'plot_marker_color': 'carrot'}.items())
        with assert_raises(ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check field validation
        data_dict = dict(self.base_data_dict.items() + {'title' : 'test_f', 'utf_grid_title': 'carrot'}.items())
        with assert_raises(ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)


    @patch('ckan.lib.helpers.flash')
    def test_update_view_action_success(self, flash_mock):
        """Test the create view action directly (successfull test)"""
        resource_view_create = toolkit.get_action('resource_view_create')
        resource_view_update = toolkit.get_action('resource_view_update')
        # First create a resource
        data_dict = dict(self.base_data_dict.items() + {'title': 'test4'}.items())
        resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Now try to update it!
        data_dict['id'] = resource_view['id']
        data_dict['longitude_field'] = 'long2'
        resource_view_update(TestViewCreated.context, data_dict)
        # Check we have lat/long values. This is done more extensively in test_actions.
        metadata = MetaData()
        table = Table(self.resource['resource_id'], metadata, autoload=True, autoload_with=TestViewCreated.engine)
        s = select([
            table.c['latitude'],
            table.c['long2'],
            func.st_x(table.c['_geom']).label('x'),
            func.st_y(table.c['_geom']).label('y'),
        ]).where(table.c['_the_geom_webmercator'] != None)
        r = TestViewCreated.engine.execute(s)
        try:
            assert_equal(r.rowcount, 2)
            for row in r:
                assert_equal(float(row['x']), float(row['long2']))
                assert_equal(float(row['y']), float(row['latitude']))
        except:
            raise
        finally:
            r.close()
        # Check we have a message to inform us all went well
        assert_true(flash_mock.called)
        assert_equal(flash_mock.call_args[1]['category'], 'alert-success')

    @patch('ckan.lib.helpers.flash')
    def test_update_view_action_failure(self, flash_mock):
        """Test the create view action directly (failure test)"""
        resource_view_create = toolkit.get_action('resource_view_create')
        resource_view_update = toolkit.get_action('resource_view_update')
        # First create a resource
        data_dict = dict(self.base_data_dict.items() + {'title': 'test4224'}.items())
        resource_view = resource_view_create(TestViewCreated.context, data_dict)
        data_dict['id'] = resource_view['id']
        # Now test an update - Check latitude must be numeric
        data_dict['latitude_field'] = 'text'
        with assert_raises(ValidationError):
            resource_view_update(TestViewCreated.context, data_dict)
        # Check latitude must be within range
        data_dict['latitude_field'] = 'big'
        with assert_raises(ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # Check longitude must be numeric
        data_dict['latitude_field'] = 'latitude'
        data_dict['longitude_field'] = 'text'
        with assert_raises(ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # Check longitude must be within range
        data_dict['longitude_field'] = 'big'
        with assert_raises(ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # Check heat map intensity must be between 0 and 1
        data_dict['longitude_field'] = 'longitude'
        data_dict['heat_intensity'] = 2
        with assert_raises(ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # Check color validation
        data_dict['heat_intensity'] = 0.1
        data_dict['plot_marker_color'] = 'color'
        with assert_raises(ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # Check field validation
        data_dict['plot_marker_color'] = '#FFFFFF'
        data_dict['utf_grid_title'] = 'carrot'
        with assert_raises(ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # To ensure we didn't mess up above, clean up and check it validates!
        data_dict['utf_grid_title'] = '_id'
        resource_view = resource_view_update(TestViewCreated.context, data_dict)



    def test_delete_view_action(self):
        """Test the delete view action directly"""
        # There is nothing to test because the action doesn't currently do anything.
        pass




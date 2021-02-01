import pytest
from ckan.plugins import toolkit
from ckanext.tiledmap.lib.validators import colour_validator, float_01_validator, \
    is_datastore_field, is_view_id
from mock import MagicMock, patch


def test_colour_validator():
    assert colour_validator(u'#AA55FF', MagicMock()) == u'#AA55FF'
    assert colour_validator(u'AA55FF', MagicMock()) == u'#AA55FF'
    assert colour_validator(u'#A5F', MagicMock()) == u'#A5F'
    assert colour_validator(u'A5F', MagicMock()) == u'#A5F'

    with pytest.raises(toolkit.Invalid):
        colour_validator(u'#AAGG00', MagicMock())

    with pytest.raises(toolkit.Invalid):
        colour_validator(u'AAGG00', MagicMock())

    with pytest.raises(toolkit.Invalid):
        colour_validator(u'#AG0', MagicMock())

    with pytest.raises(toolkit.Invalid):
        colour_validator(u'AG0', MagicMock())

    with pytest.raises(toolkit.Invalid):
        colour_validator(u'X', MagicMock())

    with pytest.raises(toolkit.Invalid):
        colour_validator(u'#XXYYZZ', MagicMock())


def test_float_01_validator():
    assert float_01_validator(0.5, MagicMock()) == 0.5
    assert float_01_validator(0, MagicMock()) == 0
    assert float_01_validator(1, MagicMock()) == 1
    assert float_01_validator(u'0.5', MagicMock()) == 0.5

    with pytest.raises(toolkit.Invalid):
        assert float_01_validator(-1, MagicMock())

    with pytest.raises(toolkit.Invalid):
        assert float_01_validator(2, MagicMock())

    with pytest.raises(toolkit.Invalid):
        assert float_01_validator(1.1, MagicMock())

    with pytest.raises(toolkit.Invalid):
        assert float_01_validator(-0.1, MagicMock())


@pytest.mark.filterwarnings(u'ignore::sqlalchemy.exc.SADeprecationWarning')
@pytest.mark.usefixtures(u'clean_db', u'with_request_context')
def test_is_datastore_field_valid():
    # setup the global env
    toolkit.g.resource = MagicMock()

    fields = {u'beans', u'lemons'}
    mock_get_fields = MagicMock(return_value=fields)
    with patch(u'ckanext.tiledmap.lib.validators.get_resource_datastore_fields', mock_get_fields):
        value = [u'beans', u'lemons']
        assert is_datastore_field(value, MagicMock()) == value


@pytest.mark.filterwarnings(u'ignore::sqlalchemy.exc.SADeprecationWarning')
@pytest.mark.usefixtures(u'clean_db', u'with_request_context')
def test_is_datastore_field_invalid():
    # setup the global env
    toolkit.g.resource = MagicMock()

    fields = {u'beans', u'lemons'}
    mock_get_fields = MagicMock(return_value=fields)
    with patch(u'ckanext.tiledmap.lib.validators.get_resource_datastore_fields', mock_get_fields):
        value = [u'goats']
        with pytest.raises(toolkit.Invalid, match=u'Invalid parameters: goats'):
            is_datastore_field(value, MagicMock())


@pytest.mark.filterwarnings(u'ignore::sqlalchemy.exc.SADeprecationWarning')
@pytest.mark.usefixtures(u'clean_db', u'with_request_context')
def test_is_datastore_field_mixed():
    # setup the global env
    toolkit.g.resource = MagicMock()

    fields = {u'beans', u'lemons'}
    mock_get_fields = MagicMock(return_value=fields)
    with patch(u'ckanext.tiledmap.lib.validators.get_resource_datastore_fields', mock_get_fields):
        value = [u'beans', u'goats', u'lemons', u'armpits']
        with pytest.raises(toolkit.Invalid, match=u'Invalid parameters: goats,armpits'):
            is_datastore_field(value, MagicMock())


def test_is_view_id_valid():
    mock_views = [dict(id=u'beans'), dict(id=u'lemons'), dict(id=u'goats')]

    mock_toolkit = MagicMock(get_action=MagicMock(return_value=MagicMock(return_value=mock_views)))
    with patch(u'ckanext.tiledmap.lib.validators.toolkit', mock_toolkit):
        view_id = u'lemons'
        assert is_view_id(view_id, MagicMock()) == view_id


@pytest.mark.filterwarnings(u'ignore::sqlalchemy.exc.SADeprecationWarning')
@pytest.mark.usefixtures(u'clean_db', u'with_request_context')
def test_is_view_id_invalid():
    toolkit.g.resource = MagicMock()
    mock_views = [dict(id=u'beans'), dict(id=u'lemons'), dict(id=u'goats')]

    mock_get_action = MagicMock(return_value=MagicMock(return_value=mock_views))
    with patch(u'ckanext.tiledmap.lib.validators.toolkit.get_action', mock_get_action):
        view_id = u'bananas'
        with pytest.raises(toolkit.Invalid):
            is_view_id(view_id, MagicMock())

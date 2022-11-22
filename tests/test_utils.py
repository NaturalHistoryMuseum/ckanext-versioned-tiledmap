from ckanext.tiledmap.lib.utils import get_resource_datastore_fields
from unittest.mock import patch, MagicMock


def test_get_resource_datastore_fields():
    expected_fields = {'beans', 'lemons', 'goats'}
    result = {'fields': [dict(id=field) for field in expected_fields]}
    mock_toolkit = MagicMock(
        get_action=MagicMock(return_value=MagicMock(return_value=result))
    )
    with patch('ckanext.tiledmap.lib.utils.toolkit', mock_toolkit):
        assert get_resource_datastore_fields(MagicMock()) == expected_fields

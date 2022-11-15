from functools import wraps
from unittest.mock import patch, MagicMock

from ckanext.tiledmap.routes._helpers import extract_q_and_filters


def mock_params(q=None, filters=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            params = {}
            if q is not None:
                params['q'] = q
            if filters is not None:
                params['filters'] = filters

            mock_toolkit = MagicMock(request=MagicMock(params=params))

            with patch('ckanext.tiledmap.routes._helpers.toolkit', mock_toolkit):
                return f(*args, **kwargs)

        return wrapper

    return decorator


class TestExtractQAndFilters:
    @mock_params()
    def test_missing_both(self):
        q, filters = extract_q_and_filters()
        assert q is None
        assert filters is None

    @mock_params(q='beans')
    def test_only_q(self):
        q, filters = extract_q_and_filters()
        assert q == 'beans'
        assert filters is None

    @mock_params(filters='colour:green')
    def test_only_filters(self):
        q, filters = extract_q_and_filters()
        assert q is None
        assert filters == {'colour': ['green']}

    @mock_params(filters='colour:green|colour:red|food:banana|colour:orange')
    def test_multiple_filters(self):
        q, filters = extract_q_and_filters()
        assert q is None
        assert filters == {'colour': ['green', 'red', 'orange'], 'food': ['banana']}

    @mock_params(
        q='beans and cake', filters='colour:green|colour:red|food:banana|colour:orange'
    )
    def test_both(self):
        q, filters = extract_q_and_filters()
        assert q == 'beans and cake'
        assert filters == {'colour': ['green', 'red', 'orange'], 'food': ['banana']}

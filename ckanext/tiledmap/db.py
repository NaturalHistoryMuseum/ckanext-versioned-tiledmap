from pylons import config
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

_read_engine = None
_write_engine = None


def _get_engine(write=False):
    """Return an SQL Alchemy engine to be used by this extention."""
    if write:
        global _write_engine
        if _write_engine is None:
            # Write engine doesn't really need to keep connections open, as it happens quite rarely.
            _write_engine = create_engine(config['ckan.datastore.write_url'], poolclass=NullPool)
        return _write_engine
    else:
        global _read_engine
        if _read_engine is None:
            _read_engine = create_engine(config['ckan.datastore.read_url'])
        return _read_engine

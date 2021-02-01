from ckanext.tiledmap.lib.helpers import mustache_wrapper, dwc_field_title


def test_mustache_wrapper():
    assert mustache_wrapper(u'beans') == u'{{beans}}'


def test_dwc_field_title():
    assert dwc_field_title(u'otherCatalogNumbers') == u'Other Catalog Numbers'
    assert dwc_field_title(u'occurrenceID') == u'Occurrence ID'

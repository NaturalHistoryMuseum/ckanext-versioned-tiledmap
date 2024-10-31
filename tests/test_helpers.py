from ckanext.tiledmap.lib.helpers import dwc_field_title, mustache_wrapper


def test_mustache_wrapper():
    assert mustache_wrapper('beans') == '{{beans}}'


def test_dwc_field_title():
    assert dwc_field_title('otherCatalogNumbers') == 'Other Catalog Numbers'
    assert dwc_field_title('occurrenceID') == 'Occurrence ID'

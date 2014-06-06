# coding=UTF-8
import re
import string

from nose.tools import assert_equal
from nose.tools import assert_raises

from ckanext.tiledmap.lib.sqlgenerator import Select
from ckanext.tiledmap.lib.sqlgenerator import MissingSection

class TestSelect:
    """These test cases test the ckanext.lib.sqlgenerator SQL generator class"""
    def test_raise(self):
        """Ensures the class raises an exception if no select or from clauses are defined"""
        q = Select()
        assert_raises(MissingSection, q.to_sql)
        q1 = Select()
        q1.select_from('table')
        assert_raises(MissingSection, q.to_sql)
        q2 = Select()
        q2.select('field')
        assert_raises(MissingSection, q.to_sql)

    def test_base(self):
        """Ensure it is possible to generate a query with only a from and a select clause. Test the generated SQL."""
        q = Select()
        q.select_from('table')
        q.select('field')
        assert_equal(q.to_sql(), "SELECT field FROM table")

    def test_all_sections(self):
        """Ensure it is possible to generate a query with all sections"""
        q = Select()
        q.select_from('table')
        q.distinct_on('another_field')
        q.select('field')
        q.where('number = 1')
        q.order_by('way ASC')
        q.group_by('group')
        assert_equal(q.to_sql(), "SELECT DISTINCT ON (another_field) field FROM table WHERE (number = 1) GROUP BY group ORDER BY way ASC")

    def test_all_sections_multiple(self):
        """Ensure it is possible to use multiple values for all sections"""
        q = Select()
        q.select_from('table1')
        q.select_from('table2')
        q.distinct_on('fielda')
        q.distinct_on('fieldb')
        q.select('field1')
        q.select('field2')
        q.where('number1 = 1')
        q.where('number2 = 2')
        q.order_by('way1 ASC')
        q.order_by('way2 ASC')
        q.group_by('group1')
        q.group_by('group2')
        assert_equal(q.to_sql(), ("SELECT DISTINCT ON (fielda, fieldb) field1, field2 FROM table1, table2 WHERE (number1 = 1) AND (number2 = 2)"
            " GROUP BY group1, group2 ORDER BY way1 ASC, way2 ASC"))

    def test_global_identifier(self):
        """Test the global identifier context can be used in all sections"""
        q = Select(identifiers={'table': 'table_name', 'field': 'field_name'})
        q.select_from('{table}')
        q.distinct_on('{field}')
        q.select('{field}')
        q.where('{field} = 1')
        q.order_by('{field} ASC')
        q.group_by('{field}')
        assert_equal(q.to_sql(), 'SELECT DISTINCT ON ("field_name") "field_name" FROM "table_name" WHERE ("field_name" = 1) GROUP BY "field_name" ORDER BY "field_name" ASC')

    def test_global_value(self):
        """Test the global value context can be used in all relevant sections"""
        q = Select(values={'val1': 'carrot cake', 'val2': '32'})
        q.select_from('table')
        q.select('field')
        q.where('f1 = {val1}')
        q.where('f2 = {val2}')
        assert_equal(q.to_sql(), "SELECT field FROM table WHERE (f1 = 'carrot cake') AND (f2 = '32')")

    def test_local_identifier(self):
        """Test local identifier context can be used in all sections, and that it overwrites the global context"""
        q = Select(identifiers={'table': 'table_name', 'field': 'field_name'})
        q.select_from('{table}')
        q.distinct_on('{field}')
        q.distinct_on('{field}', identifiers={'field': 'another_field'})
        q.select('{field}')
        q.select('{field}', identifiers={'field': 'another_field'})
        q.where('{field} = 1')
        q.where('{field} = 2', identifiers={'field': 'another_field'})
        q.order_by('{field} ASC')
        q.order_by('{field} DESC', identifiers={'field': 'another_field'})
        q.group_by('{field}')
        q.group_by('{field}', identifiers={'field': 'another_field'})
        assert_equal(q.to_sql(), 'SELECT DISTINCT ON ("field_name", "another_field") "field_name", "another_field" FROM "table_name" WHERE ("field_name" = 1) AND ("another_field" = 2) GROUP BY "field_name", "another_field" ORDER BY "field_name" ASC, "another_field" DESC')

    def test_local_value(self):
        """Test local value context can be used in all relevant sections, and that it overwrites the global context"""
        q = Select(values={'val1': 'carrot cake'})
        q.select_from('table')
        q.select('field')
        q.where('f1 = {val1}')
        q.where('f2 = {val1}', values={'val1': 'apple pie'})
        assert_equal(q.to_sql(), "SELECT field FROM table WHERE (f1 = 'carrot cake') AND (f2 = 'apple pie')")

    def test_identifier_tuple(self):
        """Test global/local identifiers can be a tuple defining table.field"""
        q = Select(identifiers={'field': ('t1', 'f1')})
        q.select_from('table')
        q.distinct_on('{field}')
        q.distinct_on('{field}', identifiers={'field': ('t2', 'f2')})
        q.select('{field}')
        q.select('{field}', identifiers={'field': ('t2', 'f2')})
        q.where('{field} = 1')
        q.where('{field} = 2', identifiers={'field': ('t2', 'f2')})
        q.order_by('{field} ASC')
        q.order_by('{field} DESC', identifiers={'field': ('t2', 'f2')})
        q.group_by('{field}')
        q.group_by('{field}', {'field': ('t2', 'f2')})
        assert_equal(q.to_sql(), 'SELECT DISTINCT ON ("t1"."f1", "t2"."f2") "t1"."f1", "t2"."f2" FROM table WHERE ("t1"."f1" = 1) AND ("t2"."f2" = 2) GROUP BY "t1"."f1", "t2"."f2" ORDER BY "t1"."f1" ASC, "t2"."f2" DESC')

    def test_identifier_cast(self):
        """Test that non-string values are cast to string for identifiers"""
        q = Select(identifiers={'field': 12})
        q.select_from('table')
        q.select('{field}')
        assert_equal(q.to_sql(), 'SELECT "12" FROM table')

    def test_numeric_values(self):
        """Test that strings get quoted and numeric (int or float) do not."""
        q = Select(values={'val1': '12', 'val2': 12, 'val3': 12.1})
        q.select_from('table')
        q.select('field')
        q.where('f1 = {val1}')
        q.where('f2 = {val2}')
        q.where('f3 = {val3}')
        assert_equal(q.to_sql(), "SELECT field FROM table WHERE (f1 = '12') AND (f2 = 12) AND (f3 = 12.1)")

    def test_identifier_escape(self):
        """Test that identifier names are properly and safely escaped"""
        valid = string.ascii_letters + '0123456789-_ (),.'
        test1 = '"\'!"%&*;:@#~[]{}\|/?<>' + valid
        test2 = u'ÃÆÔöğ' + chr(10) + valid
        q = Select(identifiers={'table': test1})
        q.select_from('{table}')
        q.select('{field}', identifiers={'field': test2})
        assert_equal(q.to_sql(), 'SELECT "' + valid + '" FROM "' + valid + '"')

    def test_value_escape(self):
        """Test that values are properly and safely escaped"""
        valid = string.ascii_letters + '0123456789-_ (),.'
        test1 = '"\'!"£$%^&*;:@#~[]{}`¬\|/?<>' + valid
        test2 = u'ÃÆÔöğ' + chr(10) + valid
        q = Select(values={'v1': test1})
        q.select_from('table')
        q.select('field')
        q.where('f1 = {v1}')
        q.where('f2 = {v2}', values={'v2': test2})
        assert_equal(q.to_sql(), 'SELECT field FROM table WHERE (f1 = \'' + valid + '\') AND (f2 = \'' + valid + '\')')

    def test_query_as_value(self):
        """Test that it is possible to use a query as a value"""
        q1 = Select()
        q1.select_from('t1')
        q1.select('f1')
        q2 = Select(values={'query': q1})
        q2.select_from('({query}) AS sub_query')
        q2.select('*')
        assert_equal(q2.to_sql(), 'SELECT * FROM (SELECT f1 FROM t1) AS sub_query')

    def test_option_nl(self):
        """Test that the nl option works"""
        q = Select(options={'nl': True})
        q.select_from('table')
        q.distinct_on('another_field')
        q.select('field')
        q.where('number = 1')
        q.order_by('way ASC')
        q.group_by('group')
        assert_equal(q.to_sql(), "SELECT DISTINCT ON (another_field) field\nFROM table\nWHERE (number = 1)\nGROUP BY group\nORDER BY way ASC")

    def test_option_compact(self):
        """Test that the compact option works"""
        # Without compact
        q = Select()
        q.select_from('table')
        q.select('field')
        q.where("n = 1 \n  AND   n = 2")
        assert_equal(q.to_sql(), "SELECT field FROM table WHERE (n = 1 \n  AND   n = 2)")
        # With compact
        q = Select(options={'compact': True})
        q.select_from('table')
        q.select('field')
        q.where("n = 1 \n  AND   n = 2")
        assert_equal(q.to_sql(), "SELECT field FROM table WHERE (n = 1 AND n = 2)")
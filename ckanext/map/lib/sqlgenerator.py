import re
import string

# Note: As explained here, directly generating SQL is a bad idea. However the tile server expects SQL directly to
# allow us to filter the generated points on the tile.
#
# We could move the SQL generation to the tile server front-end, but the problem would remain - this is an issue with
# Mapnik itself.
#
# Creating views for each query is not viable.


class Select:
    """Class used to generate PostgreSQL compatible SELECT SQL queries.

        Generating SQL is generally considered *a bad idea* because
        only the database server knows how to escape identifiers and fields
        for the given server & version. In addition it is all to easy to introduce
        escaping bugs. For these reason queries should always be sent to the server
        using the proper API, with parameters separated from the expression.

        There are cases however where the only possible approach is to generate SQL.

        In order to minimize the risk of wrongly escape identifiers or values, this generator
        enforces the following rules:

        - Both identifiers and values must be in ASCII. Non-ascii characters are stripped out;
        - Identifiers can only contain alphanumeric characters, underscores, dashes and spaces;
        - Values can only only contain alphanumeric characters, underscores, dashes and spaces.

        Available options:
          nl: Defaults to False. If True, will add a newline between each of the SQL query sections.
          compact: Defaults to False. If True, will remove all newlines and consecutive white spaces
                   from expressions (but not from identifiers/values). This is not a parser - if you
                   hand-code values into your expressions, those will get compacted too!
    """

    def __init__(self, options=None, identifiers=None, values=None):
        """ Create a new SqlGenerator
        @param options: Dictionary of options
        @param identifiers: Dictionary of identifier label to value
        @param values: Dictionary of value label to value
        """
        options = options or {}
        self._global_context = (identifiers or {}, values or {})
        self._options = dict({'nl': False, 'compact': False}.items() + options.items())
        self._query = {
            'from': [],
            'select': [],
            'distinct_on': [],
            'where': [],
            'order_by': [],
            'group_by': []
        }

    def to_sql(self):
        """Generate the SQL represented by this query.

        @raise: MissingSection
        @return: The SQL string
        """
        # Ensure we have required sections
        if len(self._query['from']) == 0:
            raise MissingSection('from')
        if len(self._query['select']) == 0:
            raise MissingSection('select')

        # Build select clause
        query = []
        query.append("SELECT")
        if len(self._query['distinct_on']):
            query[0] = query[0] + " DISTINCT ON (" + ', '.join(self._sql_section('distinct_on')) + ")"
        query[0] = query[0] + " " + ', '.join(self._sql_section('select'))
        query.append('FROM ' + ', '.join(self._sql_section('from')))
        if len(self._query['where']):
            query.append("WHERE (" + ') AND ('.join(self._sql_section('where')) + ')')
        if len(self._query['group_by']):
            query.append("GROUP BY " + ', '.join(self._sql_section('group_by')))
        if len(self._query['order_by']):
            query.append("ORDER BY " + ', '.join(self._sql_section('order_by')))
        if self._options['nl']:
            return "\n".join(query)
        else:
            return " ".join(query)

    def select_from(self, expr, identifiers=None, values=None):
        """ Add a table/expression to the from clause of the query
        @param from_expr: The from clause
        @param identifiers: Dictionary of identifier label to value for the from clause only
        @param values: Dictionary of value label to value for the from clause only
        @return: self
        """
        return self._add_expr('from', expr, identifiers, values)

    def distinct_on(self, expr, identifiers=None, values=None):
        """ Add a distinct on clause to the query
        @param expr: Expression to add to the distinct on
        @param identifiers: Dictionary of identifier label to value for that expression
        @param values: Dictionaory of label to value for that expression
        @return: self
        """
        return self._add_expr('distinct_on', expr, identifiers, values)

    def select(self, expr, identifiers=None, values=None):
        """ Add a field/expression to the select clause
        @param expr: An expression for the select clause
        @param identifiers: Dictionary of identifier label to value for that expression
        @param values: Dictionary of identifier value to value for that expression
        @return: self
        """
        return self._add_expr('select', expr, identifiers, values)

    def where(self, expr, identifiers=None, values=None):
        """ Add an expression to the where clause

        Where clauses are always joined with an 'AND' operator

        @param expr: An expression for the select clause
        @param identifiers: Dictionary of identifier label to value for that expression
        @param values: Dictionary of identifier value to value for that expression
        @return: self
        """
        return self._add_expr('where', expr, identifiers, values)

    def order_by(self, expr, identifiers=None, values=None):
        """ Add an order by clause
        @param expr: An expression for the order by clause
        @param identifiers: Dictionary of identifier label to value for that expression
        @param values: Dictionary of identifier value to value for that expression
        @return: self
        """
        return self._add_expr('order_by', expr, identifiers, values)

    def group_by(self, expr, identifiers=None, values=None):
        """ Add a group by clause
        @param expr: An expression for the group by clause
        @param identifiers: Dictionary of identifier label to value for that expression
        @param values: Dictionary of identifier value to value for that expression
        @return: self
        """
        return self._add_expr('group_by', expr, identifiers, values)

    def _add_expr(self, part, expr, identifiers, values):
        """ Generic function for adding a new expression to a part (from, where, etc.) of the query
        @param type: from, select, where, order_by, group_by
        @param expr: The expression
        @param identifiers: Dictionary of identifier label to value for that expression
        @param values: Dictionary of value label to value for that expression
        @return: self
        """
        local_context = self._get_context(identifiers, values)
        self._query[part].append((expr, local_context))
        return self

    def _get_context(self, identifiers, values):
        """Create a context by expanding the default context with the given one
        @param identifiers: Dictionary of identifier label to value
        @param values: Dictionary of value label to value
        @return: Context defined as tuple of identifier dictionary and value dictionary
        """
        identifiers = identifiers or {}
        values = values or {}
        context_identifiers = dict(self._global_context[0].items() + identifiers.items())
        context_values = dict(self._global_context[1].items() + values.items())
        return context_identifiers, context_values

    def _get_replacements(self, context):
        """ Get the escaped replacement strings from a given context
        @param context: Tuple of identifier and value dictionaries
        @return: Dictionary of label to escaped identifier/value
        """
        identifiers = {}
        for label, val in context[0].items():
            if type(val) is tuple:
                identifiers[label] = '"' + self._clean_string(val[0]) + '".' + '"' + self._clean_string(val[1]) + '"'
            else:
                identifiers[label] = '"' + self._clean_string(val) + '"'
        values = {}
        for label, val in context[1].items():
            if type(val) in [int, float]:
                values[label] = str(val)
            elif isinstance(val, Select):
                values[label] = val.to_sql()
            else:
                values[label] = "'" + self._clean_string(val) + "'"

        return dict(identifiers.items() + values.items())

    def _sql_section(self, section):
        """Return a list of expressions in the given section for the current query, with identifiers and values replaced

        @param section: name of the section
        @return: A list of elements (with identifiers/values replaced)
        """
        result = []
        for i in self._query[section]:
            s = i[0]
            if self._options['compact']:
                s = re.sub("[\s\n]+", ' ', s)
            result.append(s.format(**self._get_replacements(i[1])))

        return result

    def _clean_string(self, val):
        """Clean up a string by ensuring it's an ascii strings with characters in -_a-zA-Z0-9<space> only

        @param val: String to clean up
        @return: The cleaned up string
        """
        if type(val) not in [str, unicode]:
            val = str(val)

        clean_str = ''
        for c in val:
            if (c not in string.ascii_letters) and (c not in [' ', '-', '_', '0', '1', '2', '3', '4', '5', '6', '7',
                                                              '8', '9', '(', ')', '.', ',']):
                continue
            clean_str = clean_str + c
        return clean_str


class MissingSection(Exception):
    """Exception raised when there is missing section preventing the generation of meaningfull SQL (from or select)

    Attributes:
      section: Missing section name
    """

    def __init__(self, section):
        """ Create a new MissingSection defining the missing section
        @param section: Name of the missing section (from or select)
        """
        self.section = section

    def __str__(self):
        return "Missing required SQL section: {}".format(self.section)

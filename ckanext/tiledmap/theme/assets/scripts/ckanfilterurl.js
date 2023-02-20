this.tiledmap = this.tiledmap || {};

(function (my, $) {
  /**
   * Class used to parse and create URLs with a query string parameter 'filter' build as
   * 'name:value|....'
   */
  my.CkanFilterUrl = function (input_url) {
    /**
     * Set up the object
     */
    this.initialize = function () {
      if (typeof input_url !== 'undefined') {
        this.set_url(input_url);
      } else {
        this.base = '';
        this.qs = {};
      }
    };

    /**
     * Set this object's URL
     */
    this.set_url = function (url) {
      var parts = url.split('?');
      this.base = parts[0];
      this.qs = {};
      if (parts.length > 1) {
        var qs_idx = parts[1].split('&');
        for (var i in qs_idx) {
          var p = qs_idx[i].split('=');
          p[0] = decodeURIComponent(p[0]);
          p[1] = decodeURIComponent(p[1]);
          this.qs[p[0]] = p[1];
        }
        if (typeof this.qs['filters'] !== 'undefined') {
          this.set_filters(this.qs['filters']);
        }
      }

      return this;
    };

    /**
     * Add a filter to the current URL.
     */
    this.add_filter = function (name, value) {
      if (typeof this.qs['filters'] === 'undefined') {
        this.qs['filters'] = {};
      }
      if (typeof this.qs['filters'][name] === 'undefined') {
        this.qs['filters'][name] = [];
      }
      if ($.isArray(value)) {
        this.qs['filters'][name] = this.qs['filters'][name].concat(value);
      } else {
        this.qs['filters'][name].push(value);
      }

      return this;
    };

    /**
     * Remove filter from the current url
     */
    this.remove_filter = function (name) {
      if (typeof this.qs['filters'] !== 'undefined') {
        delete this.qs['filters'][name];
        if ($.isEmptyObject(this.qs['filters'])) {
          delete this.qs['filters'];
        }
      }
      return this;
    };

    /**
     * Set a filter value on the URL. If the value evaluates to false, the filter is removed
     */
    this.set_filter = function (name, value) {
      if (!value) {
        this.remove_filter(name);
      } else {
        this.add_filter(name, value);
      }

      return this;
    };

    /**
     * Set the filters of the URL. The value may be a decoded query string formated filter
     * (a:b|...), or a dictionary of name to value.
     */
    this.set_filters = function (filters) {
      delete this.qs['filters'];
      if (typeof filters === 'string' && filters) {
        var split = filters.split('|');
        for (var i in split) {
          var parts = split[i].split(':');
          if (parts.length === 2) {
            this.set_filter(parts[0], parts[1]);
          }
        }
      } else if (typeof filters === 'object') {
        for (var i in filters) {
          this.set_filter(i, filters[i]);
        }
      }
      return this;
    };

    /**
     * Returns the filter query string alone (not encoded)
     */
    this.get_filters = function () {
      if (typeof this.qs['filters'] === 'undefined') {
        return '';
      }
      var b_filter = [];
      for (var f in this.qs['filters']) {
        for (var i = 0; i < this.qs['filters'][f].length; i++) {
          b_filter.push(f + ':' + this.qs['filters'][f][i]);
        }
      }
      return b_filter.join('|');
    };

    /**
     * Return the values (as an array) of a single filter in the filter query string
     */
    this.get_filter = function (name) {
      if (!this.qs['filters'] || !this.qs['filters'][name]) {
        return [];
      }
      return this.qs['filters'][name];
    };

    /**
     * Return the URL as a string
     */
    this.get_url = function () {
      var b_qs = [];
      for (var i in this.qs) {
        var val;
        if (i === 'filters') {
          val = this.get_filters();
        } else {
          val = this.qs[i];
        }
        b_qs.push(encodeURIComponent(i) + '=' + encodeURIComponent(val));
      }

      return this.base + '?' + b_qs.join('&');
    };

    this.initialize();
  };
})(this.tiledmap, jQuery);

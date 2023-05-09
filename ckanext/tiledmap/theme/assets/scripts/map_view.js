this.tiledmap = this.tiledmap || {};

/**
 * Custom backbone view to display the Windshaft based maps.
 */
(function (my, $) {
  my.NHMMap = Backbone.View.extend({
    className: 'tiled-map',
    template:
      '<div class="tiled-map-info"></div><div class="panel sidebar"><a class="close">x</a></div><div class="panel map"></div>',

    /**
     * This is only called once.
     */
    initialize: function () {
      this.el = $(this.el);
      // Setup options
      this.map_ready = false;
      this.visible = true;
      this.fetch_count = 0;
      this.resource_id = this.options.resource_id;
      this.view_id = this.options.view_id;
      this.filters = this.options.filters;
      this.countries = null;
      this.layers = {};
      // Setup the sidebar
      this.sidebar_view = new my.PointDetailView();
      // Handle window resize
      $(window.parent).resize($.proxy(this, '_resize'));
      this._resize();
      // Handle on pop state
      $(window.parent).on('popstate', $.proxy(this, '_popstate'));
    },

    /**
     * Render the map
     *
     * This is called when for the initial map rendering and when the map needs
     * a full refresh (eg. filters are applied).
     */
    render: function () {
      var out = Mustache.render(this.template);
      this.el.html(out);
      this.$map = this.el.find('.panel.map');
      // Add close button handler
      this.el.find('.close').click(this.closeSidebar);
      $('.panel.sidebar', this.el).append(this.sidebar_view.el);
      this.map_ready = false;
      this._fetchMapInfo(
        $.proxy(function (info) {
          this.map_info = info;
          this.map_info.draw = true;
          this.map_ready = true;
          this._setupMap();
          this.redraw();
          if (this.visible) {
            this.show();
          }
        }, this),
        $.proxy(function (message) {
          this.map_info = {
            draw: false,
            error: message,
          };
          // The map _is_ ready, even if all it displays is an error message.
          this.map_ready = true;
          if (this.visible) {
            this.show();
          }
        }, this),
      );
    },

    /**
     * Show the map
     *
     * Called when the map visulisation is selected.
     */
    show: function () {
      var $rri = $('.tiled-map-info', this.el);
      if (this.map_ready) {
        if (this.map_info.draw) {
          this.updateRecordCounter();
        } else {
          $rri.html(this.map_info.error);
        }
      } else {
        $rri.html('Loading...');
      }

      /* If the div was hidden, Leaflet needs to recalculate some sizes to display properly */
      if (this.map_ready && this.map) {
        this._resize();
        this.map.invalidateSize();
        if (this._zoomPending && this.state.get('autoZoom')) {
          this._zoomToFeatures();
          this._zoomPending = false;
        }
      }
      this.el.css('display', 'block');
      this.visible = true;
    },

    /**
     * Update the record counter
     */
    updateRecordCounter: function () {
      var $rri = $('.tiled-map-info', this.el);
      var template = [
        'Displaying <span class="doc-count">{{geoRecordCount}}</span>',
        ' of ',
        '</span><span class="doc-count">{{recordCount}}</span>',
        'records',
      ].join(' ');
      $rri.html(
        Mustache.render(template, {
          recordCount: this.map_info.total_count
            ? this.map_info.total_count.toString()
            : '0',
          geoRecordCount: this.map_info.geom_count
            ? this.map_info.geom_count.toString()
            : '0',
        }),
      );
    },

    /**
     * Hide the map.
     *
     * This is called when the grid or graph views are selected.
     */
    hide: function () {
      this.el.css('display', 'none');
      this.visible = false;
    },

    /**
     * Called when the window is resized to set the map size
     */
    _resize: function () {
      if (this.controls && this.controls['fullScreen'].is_full_screen) {
        $('div.panel.map, div.panel.sidebar', this.el).height(
          $(window.parent).height() * 0.9,
        );
      } else {
        $('div.panel.map, div.panel.sidebar', this.el).height(
          $(window.parent).height() * 0.75,
        );
      }
      if (this.map) {
        this.map.invalidateSize();
      }
    },

    /**
     * Called when on popstate. Restore the previous __geo__ filter.
     */
    _popstate: function (e) {
      if (e.originalEvent.state && e.originalEvent.state.geom) {
        this.setGeom(e.originalEvent.state.geom, true);
      } else {
        var geom_t = new my.CkanFilterUrl(
          window.parent.location.href,
        ).get_filter('__geo__');
        var geom = null;
        if (geom_t.length > 0) {
          // TODO: We don't support multi-value filters.
          geom = JSON.parse(geom_t[0]);
        }
        this.setGeom(geom, true);
      }
    },

    /**
     * Internal map setup.
     *
     * This is called internally when the map is initially setup, or when it needs
     * a full refresh (eg. filters are applied)
     */
    _setupMap: function () {
      var self = this;
      var bounds = false;
      if (typeof this.map !== 'undefined') {
        bounds = this.map.getBounds();
        this.disablePlugins();
        this.map.remove();
      }
      /* Fix map jump issue, see: https://github.com/Leaflet/Leaflet/issues/1228 */
      L.Map.addInitHook(function () {
        return L.DomEvent.off(
          this._container,
          'mousedown',
          this.keyboard._onMouseDown,
        );
      });
      this.map = new L.Map(this.$map.get(0), {
        worldCopyJump: true,
        trackResize: false,
        minZoom: this.map_info.zoom_bounds.min,
        maxZoom: this.map_info.zoom_bounds.max,
      });
      if (this.map_info.geom_count > 0 || !bounds) {
        bounds = this.map_info.bounds;
      }
      this.map.fitBounds(this.map_info.bounds, {
        animate: false,
        maxZoom: this.map_info.initial_zoom.max,
      });
      if (this.map.getZoom() < this.map_info.initial_zoom.min) {
        var center = this.map.getCenter();
        this.map.setView(center, this.map_info.initial_zoom.min);
      }
      L.tileLayer(this.map_info.tile_layer.url, {
        attribution: this.map_info.tile_layer.attribution,
        opacity: this.map_info.tile_layer.opacity,
        noWrap: !this.map_info.repeat_map,
      }).addTo(this.map);

      // Set up the controls available to the map. These are assigned during redraw.
      this.controls = {
        drawShape: new my.DrawShapeControl(
          this,
          this.map_info.control_options['drawShape'],
        ),
        mapType: new my.MapTypeControl(
          this,
          this.map_info.control_options['mapType'],
        ),
        fullScreen: new my.FullScreenControl(
          this,
          this.map_info.control_options['fullScreen'],
        ),
        miniMap: new my.MiniMapControl(
          this,
          this.map_info.control_options['miniMap'],
        ),
      };

      // Set up the plugins available to the map. These are assigned during redraw.
      this.plugins = {
        tooltipInfo: new my.TooltipPlugin(
          this,
          this.map_info.plugin_options['tooltipInfo'],
        ),
        tooltipCount: new my.TooltipPlugin(
          this,
          this.map_info.plugin_options['tooltipCount'],
        ),
        pointInfo: new my.PointInfoPlugin(
          this,
          this.map_info.plugin_options['pointInfo'],
        ),
      };

      // Setup handling of draw events to ensure plugins work nicely together
      this.map.on('draw:created', function (e) {
        self.setGeom(e.layer.toGeoJSON().geometry);
      });
      this.map.on('draw:drawstart', function (e) {
        self.invoke('active', false);
        self.layers['plot'].setOpacity(0.5);
      });
      this.map.on('draw:drawstop', function (e) {
        self.invoke('active', true);
        self.layers['plot'].setOpacity(1);
      });
      this._resize();
    },

    /**
     * Internal method to fetch extra map info (such as the number of records with geoms)
     *
     * Called internally during render, and calls the provided callback function on success
     * after updating map_info
     */
    _fetchMapInfo: function (callback, error_cb) {
      this.fetch_count++;

      var params = {
        resource_id: this.resource_id,
        view_id: this.view_id,
        fetch_id: this.fetch_count,
      };

      var filters = new my.CkanFilterUrl().set_filters(this.filters.fields);
      if (this.filters.geom) {
        filters.set_filter('__geo__', JSON.stringify(this.filters.geom));
      }
      params['filters'] = filters.get_filters();

      if (this.filters.q) {
        params['q'] = this.filters.q;
      }

      if (typeof this.jqxhr !== 'undefined' && this.jqxhr !== null) {
        this.jqxhr.abort();
      }

      this.jqxhr = $.ajax({
        url: ckan.SITE_ROOT + '/map-info',
        type: 'GET',
        data: params,
        success: $.proxy(function (data, status, jqXHR) {
          this.jqxhr = null;
          // Ensure this is the result we want, not a previous query!
          if (data.fetch_id === this.fetch_count) {
            if (typeof data.geospatial !== 'undefined' && data.geospatial) {
              callback(data);
            } else {
              error_cb('This data does not have geospatial information');
            }
          }
        }, this),
        error: function (jqXHR, status, error) {
          if (status !== 'abort') {
            error_cb('Error while loading the map');
          }
        },
      });
    },

    /**
     * Reload the number of records. Called when filters change without a page reload.
     */
    _refreshInfo: function () {
      var $rri = $('.tiled-map-info', this.el);
      $rri.html('Loading...');
      this._fetchMapInfo(
        $.proxy(function (info) {
          // cache the currently selected map style
          var currentMapStyle = this.map_info.map_style;
          // update the map_info property with the new data
          this.map_info = info;
          // and then write the current selection back into the object
          this.map_info.map_style = currentMapStyle;
          this.map_info.draw = true;
          this.updateRecordCounter();
          // and redraw the map
          this.redraw();
        }, this),
        function () {
          /* NO OP */
        },
      );
    },

    /**
     * Set the geom filter. This will cause the map to be redrawn and links to views to be
     * updated. If leave_window_url if false or undefined, this will also update the browser url
     * (or reload the page in older browsers).
     */
    setGeom: function (geom, leave_window_url) {
      // Get the geometry drawn
      if (!geom && !this.filters.geom) {
        return;
      }
      this.filters.geom = geom;
      // Inject the geom search term in links to all other views.
      var param = null;
      if (this.filters.geom) {
        param = JSON.stringify(this.filters.geom);
      }
      $(
        'section.module ul.view-list li.resource-view-item a',
        window.parent.document,
      ).each(function () {
        var href = new my.CkanFilterUrl($(this).attr('href'))
          .set_filter('__geo__', param)
          .get_url();
        $(this).attr('href', href);
      });
      // Inject the geom search in the browser URL.
      if (!leave_window_url) {
        var href = new my.CkanFilterUrl(window.parent.location.href)
          .set_filter('__geo__', param)
          .get_url();
        if (window.parent.history.pushState) {
          window.parent.history.pushState({ geom: geom }, '', href);
        } else {
          window.parent.location = href;
        }
      }
      // refresh the map info and redraw after
      this._refreshInfo();
    },

    /**
     * Redraw the map
     *
     * This is called to redraw the map. It is called for the initial redraw, but also
     * when the display region changes ; eg. when a shape is drawn on the map.
     *
     */
    redraw: function () {
      var self = this;
      if (!this.map_ready || !this.map_info.draw) {
        return;
      }
      // Setup tile request parameters
      var params = {};
      params['query'] = this.map_info.query_body;
      params['style'] = this.map_info.map_style;
      var style = this.map_info.map_styles[this.map_info.map_style];

      // Prepare layers
      var tile_params = $.extend({}, params);
      if (style.tile_source.params) {
        tile_params = $.extend(tile_params, style.tile_source.params);
      }
      var tile_url = style.tile_source.url + '?' + $.param(tile_params);

      for (var i in this.layers) {
        this.map.removeLayer(this.layers[i]);
      }
      this._removeAllLayers();
      if (this.filters.geom) {
        this._addLayer('selection', L.geoJson(this.filters.geom));
      }
      this._addLayer(
        'plot',
        L.tileLayer(tile_url, {
          noWrap: !this.map_info.repeat_map,
        }),
      );

      if (style.has_grid) {
        var grid_params = $.extend({}, params);
        if (style.grid_source.params) {
          grid_params = $.extend(grid_params, style.grid_source.params);
        }
        var grid_url = style.grid_source.url + '?' + $.param(grid_params);

        this._addLayer(
          'grid',
          new L.UtfGrid(grid_url, {
            resolution: style.grid_resolution,
            useJsonP: false,
            maxRequests: 4,
            pointerCursor: false,
          }),
        );
      }
      // Ensure that click events on the selection get passed to the map.
      if (typeof this.layers['selection'] !== 'undefined') {
        this.layers['selection'].on('click', function (e) {
          self.map.fire('click', e);
        });
      }

      // Update controls & plugins
      this.updateControls();
      this.updatePlugins();

      // Add plugin defined layers & call redraw on plugins.
      var extra_layers = this.invoke('layers');
      for (var i in extra_layers) {
        this._addLayer(extra_layers[i].name, extra_layers[i].layer);
      }
      this.invoke('redraw', this.layers);
    },

    /**
     * Open the sidebar.
     */
    openSidebar: function (x, y) {
      var $sb = $('.panel.sidebar', this.el);
      var width = $sb.css('max-width');
      var base_duration = 200;
      if ($sb.width() < parseInt(width)) {
        var distance = this.el.width() - x;
        if (distance < parseInt(width) + 50) {
          var diff = parseInt(width) + 50 - distance;
          var pan_duration = (base_duration * diff) / parseInt(width) / 1000.0;
          this.map.panBy([diff, 0], {
            duration: pan_duration,
            easeLinearity: 1.0,
          });
        }
      }
      $sb.stop().animate(
        {
          width: width,
        },
        {
          duration: base_duration,
          easing: 'linear',
        },
      );
    },

    /**
     * Close the sidebar
     */
    closeSidebar: function () {
      var $sb = $('.panel.sidebar', this.el);
      $sb.stop().animate(
        {
          width: 0,
        },
        {
          complete: function () {
            $sb.css('overflow-y', 'hidden');
          },
        },
      );
    },

    /**
     * This function adds a new layer to the map
     */
    _addLayer: function (name, layer) {
      if (typeof this.layers[name] !== 'undefined') {
        this.map.removeLayer(this.layers[name]);
      }
      this.layers[name] = layer;
      this.map.addLayer(layer);
    },

    /**
     * This function removes a layer from the map
     */
    _removeLayer: function (name) {
      if (typeof this.layers[name] !== 'undefined') {
        this.map.removeLayer(this.layers[name]);
        delete this.layers[name];
      }
    },

    /**
     * Removes all layers from the map
     */
    _removeAllLayers: function () {
      for (var i in this.layers) {
        this.map.removeLayer(this.layers[i]);
      }
      this.layers = {};
    },

    /**
     * Updates the controls used on the map for the current style
     */
    updateControls: function () {
      this._updateAddons(
        'controls',
        $.proxy(function (control) {
          this.map.addControl(this.controls[control]);
        }, this),
        $.proxy(function (control) {
          this.map.removeControl(this.controls[control]);
        }, this),
      );
    },

    /**
     * Updates the plugins used on this map
     */
    updatePlugins: function () {
      this._updateAddons(
        'plugins',
        $.proxy(function (plugin) {
          this.plugins[plugin].enable();
        }, this),
        $.proxy(function (plugin) {
          this.plugins[plugin].disable();
        }, this),
      );
    },

    /**
     * Disable all plugins
     */
    disablePlugins: function () {
      if (typeof this._current_addons === 'undefined') {
        this._current_addons = {};
      }
      if (typeof this._current_addons['plugins'] === 'undefined') {
        this._current_addons['plugins'] = [];
      }
      for (var i in this._current_addons['plugins']) {
        var plugin = this._current_addons['plugins'][i];
        this.plugins[plugin].disable();
      }
      this._current_addons['plugins'] = [];
    },

    /**
     * Invoke a particular hook on enabled plugins and controls
     */
    invoke: function (hook, args) {
      var ret = [];
      for (var p in this._current_addons) {
        for (var i in this._current_addons[p]) {
          var addon = this[p][this._current_addons[p][i]];
          if (typeof addon[hook] == 'function') {
            var lr = addon[hook](args);
            if ($.isArray(lr)) {
              ret = ret.concat(lr);
            } else if (typeof lr !== 'undefined') {
              ret.push(lr);
            }
          }
        }
      }
      if (ret.length > 0) {
        return ret;
      }
    },

    /**
     * Generic function for updating controls and plugins.
     */
    _updateAddons: function (type, add_cb, remove_cb) {
      if (typeof this._current_addons === 'undefined') {
        this._current_addons = {};
      }
      if (typeof this._current_addons[type] === 'undefined') {
        this._current_addons[type] = [];
      }
      var style = this.map_info.map_styles[this.map_info.map_style];
      var new_addons = [];
      if (typeof style[type] !== 'undefined') {
        for (var i in style[type]) {
          var addon = style[type][i];
          new_addons.push(addon);
          if (add_cb && $.inArray(addon, this._current_addons[type]) === -1) {
            add_cb(addon);
          }
        }
      }
      for (var i in this._current_addons[type]) {
        var addon = this._current_addons[type][i];
        if (remove_cb && $.inArray(addon, new_addons) === -1) {
          remove_cb(addon);
        }
      }
      this._current_addons[type] = new_addons;
    },
  });
})(this.tiledmap, jQuery);

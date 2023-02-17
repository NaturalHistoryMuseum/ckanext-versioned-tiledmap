this.tiledmap = this.tiledmap || {};

(function (my, $) {
  /**
   * Plugin used to display information about a clicked point
   */
  my.PointInfoPlugin = function (view, options) {
    /**
     * Enable this plugin
     */
    this.enable = function () {
      this.grid = null;
      this.isactive = true;
    };

    /**
     * Disable this plugin
     */
    this.disable = function () {
      // remove handlers
      this._disable_event_handlers();
    };

    /**
     * Activate/disactive this plugin
     * (Used for temporary pause)
     */
    this.active = function (state) {
      this.isactive = state;
    };

    /**
     * Remove event handlers
     */
    this._disable_event_handlers = function () {
      if (this.grid) {
        this.grid.off('click', $.proxy(this, '_on_click'));
      }
    };

    /**
     * redraw hanlder
     */
    this.redraw = function (layers) {
      // todo: handle click events
      this._disable_event_handlers();
      this.layers = layers;
      this.grid = layers['grid'];
      this.grid.on('click', $.proxy(this, '_on_click'));

      // todo: should we handle clicks outside the map, and remove the marker?
      // todo: should we handler the escape key and remove the marker ?
    };

    /**
     * click handler
     */
    this._on_click = function (props) {
      if (!this.isactive) {
        return;
      }
      if (typeof this.animation !== 'undefined') {
        if (this.animation_restart) {
          clearTimeout(this.animation_restart);
        }
        $(this.animation).stop();
      }
      if (this.layers['_point_info_plugin']) {
        view.map.removeLayer(this.layers['_point_info_plugin']);
        view.map.removeLayer(this.layers['_point_info_plugin_1']);
      }
      if (
        props &&
        props.data &&
        (view.map_info.repeat_map ||
          (props.latlng.lng >= -180 && props.latlng.lng <= 180))
      ) {
        // Find coordinates. The values in props.latlng is the mouse position, not the point position -
        // however it helps us know if we have clicked on a point that is wrapped around the world.
        var lat = props.data.record_latitude;
        var lng = props.data.record_longitude;
        if (props.latlng.lng > 180) {
          // Tricky because the clicking might not be within the same 360 block at the center of the marker. We must
          // test for this eventuality.
          lng = lng + Math.floor((props.latlng.lng - lng) / 360) * 360;
          if (props.latlng.lng - lng > 180) {
            lng = lng + 360;
          }
        } else if (props.latlng.lng < -180) {
          lng = lng - Math.floor((lng - props.latlng.lng) / 360) * 360;
          if (lng - props.latlng.lng > 180) {
            lng = lng - 360;
          }
        }
        // Highlight the point
        this.layers['_point_info_plugin'] = L.circleMarker([lat, lng], {
          radius: 4 /* Ideally the same as the cartoCSS version */,
          stroke: true,
          color: '#FFF',
          weight: 1,
          fill: true,
          fillColor: '#00F',
          opacity: 1,
          fillOpacity: 1,
          clickable: false,
        });
        // Create pulse layer
        this.layers['_point_info_plugin_1'] = L.circleMarker([lat, lng], {
          radius: 1,
          stroke: true,
          weight: 4,
          color: '#88F',
          fill: false,
          fillColor: '#FFF',
          fillOpacity: 1,
          clickable: false,
        });
        this._animate(this.layers['_point_info_plugin_1']);
        // Add the layers in order
        view.map.addLayer(this.layers['_point_info_plugin_1']);
        view.map.addLayer(this.layers['_point_info_plugin']);
        // Add the info in the sidebar
        props.data._resource_url = window.parent.location.pathname;
        props.data._multiple =
          options.count_field && props.data[options.count_field] > 1;
        if (
          window.parent.ckan &&
          window.parent.ckan.views.filters &&
          props.data.geo_filter
        ) {
          var filters = window.parent.ckan.views.filters.get();
          var furl = new my.CkanFilterUrl().set_filters(filters);
          furl.remove_filter('__geo__');
          furl.add_filter('__geo__', JSON.stringify(props.data.geo_filter));
          props.data._overlapping_records_filters = encodeURIComponent(
            furl.get_filters(),
          );
        }
        view.sidebar_view.render(props.data, options['template']);
        var ensure_point = view.map.latLngToContainerPoint([lat, lng]);
        view.openSidebar(ensure_point.x, ensure_point.y);
      } else {
        delete this.layers['_point_info_plugin'];
        delete this.layers['_point_info_plugin_1'];
        view.sidebar_view.render(null);
        view.closeSidebar();
      }
    };

    /**
     * Animate
     */
    this._animate = function (layer) {
      var plugin = this;
      this.$animation = $('<div></div>').css('opacity', 0);
      this.$animation.animate(
        {
          opacity: 1,
        },
        {
          duration: 750,
          easing: 'swing',
          step: function (value, fx) {
            layer.setRadius(1 + value * 19);
            layer.setStyle({ fillOpacity: 1 - value });
            layer.setStyle({ opacity: 1 - value });
          },
          complete: function () {
            plugin.animation_restart = setTimeout(function () {
              plugin.animation_restart = false;
              $.proxy(plugin, '_animate')(layer);
            }, 1000);
          },
        },
      );
    };
  };
})(this.tiledmap, jQuery);

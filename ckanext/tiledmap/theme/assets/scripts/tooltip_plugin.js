this.tiledmap = this.tiledmap || {};

(function (my, $) {
  /**
   * Plugin used to add a tooltip on point hover
   */
  my.TooltipPlugin = function (view, options) {
    /**
     * enable this plugin
     */
    this.enable = function () {
      this.grid = null;
      this.isactive = true;
      this.$el = $('<div>')
        .addClass('map-hover-tooltip')
        .css({
          display: 'none',
          position: 'absolute',
          top: 0,
          left: 0,
          zIndex: 100,
        })
        .appendTo(view.map.getContainer());
      this.hover = false;
    };

    /**
     * Disable this plugin
     */
    this.disable = function () {
      this._disable_event_handlers();
      this.$el.remove();
      this.$el = null;
    };

    /**
     * Remove event handlers
     */
    this._disable_event_handlers = function () {
      if (this.grid) {
        this.grid.off('mouseover', $.proxy(this, '_mouseover'));
        this.grid.off('mouseout', $.proxy(this, '_mouseout'));
        view.map.off('mouseout', $.proxy(this, '_mouseout'));
        this.grid = null;
      }
    };

    /**
     * Activate/disactive this plugin
     * (Used for temporary pause)
     */
    this.active = function (state) {
      this.isactive = state;
    };

    /**
     * Mouseover handler
     */
    this._mouseover = function (props) {
      if (!this.isactive) {
        return;
      }
      if (
        props &&
        props.data &&
        !view.map_info.repeat_map &&
        (props.latlng.lng < -180 || props.latlng.lng > 180)
      ) {
        return;
      }
      var count =
        options.count_field && props.data[options.count_field]
          ? props.data[options.count_field]
          : 1;
      var label = false;
      if (options.template && count === 1) {
        props._multiple = count > 1;
        props._resource_url = window.parent.location.pathname;
        label = Mustache.render(options.template, props.data.data);
      } else {
        label = count + ' record' + (count === 1 ? '' : 's');
      }
      if (label) {
        this.$el.stop().html(label);
        // Place the element with visibility 'hidden' so we can get it's actual height/width.
        this.$el.css({
          top: 0,
          left: 0,
          visibility: 'hidden',
          display: 'block',
        });
        if (typeof this.initial_opacity === 'undefined') {
          this.initial_opacity = this.$el.css('opacity'); // Store CSS value
          this.$el.css('opacity', 0);
        }
        // Tooltip placement algorithm.
        var point = view.map.latLngToContainerPoint(props.latlng);
        var width = this.$el.width();
        var height = this.$el.height();
        var map_size = view.map.getSize();
        var top, left;
        if (
          point.x > (map_size.x * 4) / 5 ||
          point.x + width + 16 > map_size.x
        ) {
          left = point.x - width - 16;
        } else {
          left = point.x + 16;
        }
        if (point.y < map_size.y / 5) {
          top = point.y + height * 0.5 + 8;
        } else {
          top = point.y - height * 1.5 - 8;
        }
        this.hover = true;
        this.$el
          .css({
            top: top,
            left: left,
            visibility: 'visible',
          })
          .stop()
          .animate(
            {
              opacity: this.initial_opacity,
            },
            {
              duration: 100,
            },
          );
      }
      // Set the mouse cursor.
      $('div.panel.map').css('cursor', 'pointer');
    };

    /**
     * Mouseout handler
     */
    this._mouseout = function () {
      if (this.hover && this.$el) {
        this.hover = false;
        this.$el.stop().animate(
          {
            opacity: 0,
          },
          {
            duration: 100,
            complete: function () {
              $(this).html('');
              $(this).css('display', 'none');
            },
          },
        );
        // Remove the mouse cursor
        $('div.panel.map').css('cursor', '');
      }
    };

    /**
     * redraw handler
     */
    this.redraw = function (layers) {
      this._disable_event_handlers();
      this.grid = layers['grid'];
      this.grid.on('mouseover', $.proxy(this, '_mouseover'));
      this.grid.on('mouseout', $.proxy(this, '_mouseout'));
      view.map.on('mouseout', $.proxy(this, '_mouseout')); // UtfGrid doesn't trigger mouseout when you leave the map
    };
  };
})(this.tiledmap, jQuery);

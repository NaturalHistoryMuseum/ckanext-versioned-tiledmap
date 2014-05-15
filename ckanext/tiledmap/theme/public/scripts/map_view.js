// Integrating the NHM Map

this.recline = this.recline || {};
this.recline.View = this.recline.View || {};

(function($, my) {
/**
 * NHMMap
 *
 * Custom backbone view to display the Windshaft based maps.
 */
my.NHMMap = Backbone.View.extend({
  className: 'recline-nhm-map',
  template: '\
    <div class="recline-map"> \
      <div class="panel map"></div> \
    </div> \
  ',

  /**
   * Initialize
   *
   * This is only called once.
   */
  initialize: function() {
    this.el = $(this.el);
    _.bindAll(this, 'render');
    this.model.queryState.bind('change', this.render);
    this.map_ready = false;
    this.visible = false;
    this.fetch_count = 0;
    // Setup the sidebar
    this.sidebar_view = new my.PointDetailView();
    this.elSidebar = this.sidebar_view.el;
  },

  /**
   * Render the map
   *
   * This is called when for the initial map rendering and when the map needs
   * a full refresh (eg. filters are applied).
   */
  render: function() {
    var out = Mustache.render(this.template);
    $(this.el).html(out);
    this.$map = this.el.find('.panel.map');
    this.map_ready = false;
    this._fetchMapInfo($.proxy(function(info){
      this.map_info = info;
      this.map_info.draw = true;
      this.map_ready = true;
      this._setupMap();
      this.redraw();
      if (this.visible){
          this.show()
      }
    }, this), $.proxy(function(message){
      this.map_info = {
        draw: false,
        error:message
      };
      // The map _is_ ready, even if all it displays is an error message.
      this.map_ready = true;
      if (this.visible){
        this.show();
      }
    }, this));
  },

  /**
   * Show the map
   *
   * Called when the map visulisation is selected.
   */
  show: function() {
    /* Update Recline's meta-info */
    $('.recline-pager').hide();

    var $rri = $('.recline-results-info');
    if (this.map_ready){
      if (this.map_info.draw){
          var template = [
            '<span class="doc-count">{{geoRecordCount}}</span>',
            ' of ',
            '</span><span class="doc-count">{{recordCount}}</span>',
            'records'
          ].join(' ');
          $rri.html(Mustache.render(template, {
            recordCount: this.model.recordCount ? this.model.recordCount.toString() : '0',
            geoRecordCount: this.map_info.geom_count ? this.map_info.geom_count.toString() : '0'
          }));
      } else {
          $rri.html(this.map_info.error);
      }
    } else {
      $rri.html('Loading...');
    }

    /* If the div was hidden, Leaflet needs to recalculate some sizes to display properly */
    if (this.map_ready && this.map){
      this.map.invalidateSize();
      if (this._zoomPending && this.state.get('autoZoom')) {
        this._zoomToFeatures();
        this._zoomPending = false;
      }
    }
    this.visible = true;
  },

  /**
   * Hide the map.
   *
   * This is called when the grid or graph views are selected.
   */
  hide: function() {
     // Restore recline pager & row count
     $('.recline-pager').show();
     var template = '</span><span class="doc-count">{{recordCount}}</span> records';
     $('.recline-results-info').html(Mustache.render(template, {
        recordCount: this.model.recordCount ? this.model.recordCount.toString() : '0'
     }));
     this.visible = false
  },

  /**
   * Internal map setup.
   *
   * This is called internally when the map is initially setup, or when it needs
   * a full refresh (eg. filters are applied)
   */
  _setupMap: function(){
    var self = this;

    if (typeof this.map !== 'undefined'){
        this.disablePlugins();
        this.map.remove();
    }
    this.map = new L.Map(this.$map.get(0));
    this.map.fitBounds(this.map_info.bounds, {
        animate: false,
        maxZoom: this.map_info.initial_zoom.max
    });
    if (this.map.getZoom() < this.map_info.initial_zoom.min) {
        var center = this.map.getCenter();
        this.map.setView(center, this.map_info.initial_zoom.min)
    }
    L.tileLayer(this.map_info.tile_layer.url, {
        opacity: this.map_info.tile_layer.opacity
    }).addTo(this.map);

    this.tilejson = {
            tilejson: '1.0.0',
            scheme: 'xyz',
            tiles: [],
            grids: [],
            formatter: function(options, data) { return 'yo' /*data._id + "/" + data.species + "/" + data.scientific_name*/ }
    };

    this.map.on('draw:created', function (e) {
      // Set the the geometry in the queryState to persist it between filter/search updates
      self.model.queryState.attributes.geom = e.layer.toGeoJSON().geometry;
      self.redraw();
    });

    this.tiles_url = '/map-tile/{z}/{x}/{y}.png';
    this.grids_url = '/map-grid/{z}/{x}/{y}.grid.json?callback={cb}';

    // Set up the controls available to the map. These are assigned during redraw.
    this.controls = {
      'drawShape': new my.DrawShapeControl(this, this.map_info.control_options['drawShape']),
      'mapType': new my.MapTypeControl(this, this.map_info.control_options['mapType'])
    }
    // Set up the plugins available to the map. These are assigned during redraw.
    this.plugins = {
      'tooltipInfo': new my.TooltipPlugin(this, this.map_info.plugin_options['tooltipInfo']),
      'tooltipCount': new my.TooltipPlugin(this, this.map_info.plugin_options['tooltipCount']),
      'pointInfo': new my.PointInfoPlugin(this, this.map_info.plugin_options['pointInfo'])
    }
  },

  /**
   * Internal method to fetch extra map info (such as the number of records with geoms)
   *
   * Called internally during render, and calls the provided callback function on success
   * after updating map_info
   */
  _fetchMapInfo: function(callback, error_cb){
    this.fetch_count++;

    var params = {
        resource_id: this.model.id,
        fetch_id: this.fetch_count
    };
    params['filters'] = JSON.stringify(this.model.queryState.attributes.filters);

    if (this.model.queryState.attributes.q){
      params['q'] = this.model.queryState.attributes.q;
    }

    if (this.model.queryState.attributes.geom) {
      params['geom'] = Terraformer.WKT.convert(this.model.queryState.attributes.geom);
    }

    if (typeof this.jqxhr !== 'undefined' && this.jqxhr !== null){
      this.jqxhr.abort();
    }

    this.jqxhr = $.ajax({
      url: ckan.SITE_ROOT + '/map-info',
      type: 'GET',
      data: params,
      success: $.proxy(function(data, status, jqXHR){
        this.jqxhr = null;
        // Ensure this is the result we want, not a previous query!
        if (data.fetch_id == this.fetch_count){
          if (typeof data.geospatial !== 'undefined' && data.geospatial){
              callback(data);
          } else {
              error_cb("This data does not have geospatial information");
          }
        }
      }, this),
      error: function(jqXHR, status, error){
        if (status != 'abort'){
          error_cb("Error while loading the map");
        }
      }
    });
  },

  /**
   * Redraw the map
   *
   * This is called to redraw the map. It is called for the initial redraw, but also
   * when the display region changes ; eg. when a shape is drawn on the map.
   *
   */
  redraw: function(){
    var self = this;
    if (!this.map_ready || !this.map_info.draw){
      return;
    }
    // Setup tile request parameters
    var params = {};
    params['filters'] = JSON.stringify(this.model.queryState.attributes.filters);
    if (this.model.queryState.attributes.q){
      params['q'] = this.model.queryState.attributes.q;
    }
    if (this.model.queryState.attributes.geom) {
      params['geom'] = Terraformer.WKT.convert(this.model.queryState.attributes.geom);
    }
    params['resource_id'] = this.model.id;
    params['style'] = this.map_info.map_style;

    // Prepare layers
    this.tilejson.tiles = [this.tiles_url + "?" + $.param(params)];
    this.tilejson.grids = [this.grids_url + "&" + $.param(params)];
    if (typeof this.layers === 'undefined'){
      this.layers = {};
    }
    for (var i in this.layers){
      this.map.removeLayer(this.layers[i]);
    }
    this.layers = {
      'selection': L.geoJson(this.model.queryState.attributes.geom),
      'plot': L.tileLayer(this.tilejson.tiles[0])
    };
    var style = this.map_info.map_styles[this.map_info.map_style];
    if (style.has_grid){
      this.layers['grid'] = new L.UtfGrid(this.tilejson.grids[0], {resolution: style.grid_resolution});
    }
    for (var i in this.layers){
      this.map.addLayer(this.layers[i]);
    }
    // Ensure that click events on the selection get passed to the map.
    this.layers['selection'].on('click', function(e) {
      self.map.fire('click', e);
    });

    // Update controls & plugins
    this.updateControls();
    this.updatePlugins();
    this.callPlugins('redraw', this.layers);
  },

  /**
   * updateControls
   *
   * Updates the controls used on the map for the current style
   */
  updateControls: function (){
    this._updateAddons('controls', $.proxy(function(control){
      this.map.addControl(this.controls[control]);
    }, this), $.proxy(function(control){
      this.map.removeControl(this.controls[control]);
    }, this));
  },

  /**
   * updatePlugins
   *
   * Updates the plugins used on this map
   */
  updatePlugins: function(){
    this._updateAddons('plugins', $.proxy(function(plugin){
      this.plugins[plugin].enable();
    }, this), $.proxy(function(plugin){
      this.plugins[plugin].disable();
    }, this));
  },

  /**
   * disablePlugins
   *
   * Disable all plugins
   */
  disablePlugins: function(){
    if (typeof this._current_addons === 'undefined'){
      this._current_addons = {};
    }
    if (typeof this._current_addons['plugins'] === 'undefined'){
      this._current_addons['plugins'] = [];
    }
    for (var i in this._current_addons['plugins']){
      var plugin = this._current_addons['plugins'][i];
      this.plugins[plugin].disable();
    }
    this._current_addons['plugins'] = [];
  },

  /**
   * callPlugins
   *
   * Invoke a particular hook on enabled plugins
   */
  callPlugins: function(hook, args){
    for (var i in this._current_addons['plugins']){
      var plugin = this.plugins[this._current_addons['plugins'][i]];
      if (typeof plugin[hook] == 'function'){
        plugin[hook](args)
      }
    }
  },

  /**
   * _updateAddons
   *
   * Generic function for updating controls and plugins.
   */
  _updateAddons: function(type, add_cb, remove_cb){
    if (typeof this._current_addons === 'undefined'){
      this._current_addons = {};
    }
    if (typeof this._current_addons[type] === 'undefined'){
      this._current_addons[type] = [];
    }
    var style = this.map_info.map_styles[this.map_info.map_style];
    var new_addons = [];
    if (typeof style[type] !== 'undefined'){
      for (var i in style[type]){
        var addon = style[type][i];
        new_addons.push(addon);
        if (add_cb && !_.contains(this._current_addons[type], addon)){
          add_cb(addon);
        }
      }
    }
    for (var i in this._current_addons[type]){
      var addon = this._current_addons[type][i];
      if (remove_cb && !_.contains(new_addons, addon)){
        remove_cb(addon);
      }
    }
    this._current_addons[type] = new_addons;
  }
});

/**
 * MapTypeControl
 *
 * Custom control interface for Leaflet allowing users to switch between map styles.
 *
 */
my.MapTypeControl = L.Control.extend({
    initialize: function(view, options) {
        this.view = view;
        L.Util.setOptions(this, options);
    },

    getItemClickHandler: function(style) {
        return $.proxy(function(e){
            var $active = $('a.active-selection', this.$bar);
            if ($active.length > 0 && $active.attr('stylecontrol') == style){
                return;
            }
            this.view.map_info.map_style = style;
            $active.removeClass('active-selection');
            $('a[stylecontrol=' + style + ']').addClass('active-selection');
            this.view.redraw();
            e.stopPropagation();
            return false;
        }, this);
    },

     onAdd: function(map){
       this.$bar = $('<div>').addClass('leaflet-bar');
       for (var style in this.view.map_info.map_styles){
           var title = this.view.map_info.map_styles[style].name;
           var icon = this.view.map_info.map_styles[style].icon;
           var $elem = $('<a></a>').attr('href', '#').attr('title', title).html(icon).attr('stylecontrol', style)
               .appendTo(this.$bar)
               .click(this.getItemClickHandler(style));
           if (style == this.view.map_info.map_style){
             $elem.addClass('active-selection')
           }
       }
       return L.DomUtil.get(this.$bar.get(0));
     }
});

/**
 * DrawShapeControl
 *
 * Control used to draw shapes on the map.
 * We only extend the base Draw control to have a uniform API.
 */
my.DrawShapeControl = L.Control.Draw.extend({
    initialize: function(view, options) {
        L.Control.Draw.prototype.initialize.call(this, options);
        L.Util.setOptions(this, options);
    }
});

/**
 * Recline sidebar view for map point information
 */
my.PointDetailView = Backbone.View.extend({
  className: 'recline-map-point-detail well',
  template: 'Click on a map point for more detail',
  initialize: function() {
    this.el = $(this.el); // Ckan expects this
    this.render();
  },
  render: function(data, template) {
    var out = '';
    if (!data){
      out = Mustache.render(this.template);
    } else if (data && !template){
      for (var i in data){
        out = i.toString() + ": " + data.toString() + "<br/>";
      }
    } else {
      out = Mustache.render(template, data);
    }
    this.el.html(out);
  }
});

/**
 * PointInfoPlugin
 *
 * Plugin used to display information about a clicked point
 */
my.PointInfoPlugin = function(view, options){
  /**
   * Enable this plugin
   */
  this.enable = function(){
    this.grid = null;
    // todo: enable detail tab
  }

  /**
   * Disable this plugin
   */
  this.disable = function(){
    // todo: remove detail tab
    // remove handlers
    this._disable_event_handlers();
  }

  /**
   * Remove event handlers
   */
  this._disable_event_handlers = function(){
    if (this.grid){
      this.grid.off('click', $.proxy(this, "_on_click"));
    }
  }

  /**
   * redraw hanlder
   */
  this.redraw = function(layers){
    // todo: handle click events
    this._disable_event_handlers();
    this.layers = layers;
    this.grid = layers['grid'];
    this.grid.on('click', $.proxy(this, "_on_click"));

    // todo: should we handle clicks outside the map, and remove the marker?
    // todo: should we handler the escape key and remove the marker ?
  }

  /**
   * click handler
   */
  this._on_click = function(props){
    if (typeof this.animation !== 'undefined'){
      if (this.animation_restart){
        clearTimeout(this.animation_restart);
      }
      $(this.animation).stop();
    }
    if (this.layers['_point_info_plugin']){
      view.map.removeLayer(this.layers['_point_info_plugin']);
      view.map.removeLayer(this.layers['_point_info_plugin_1']);
    }
    if (props && props.data){
      // Find coordinates. The values in props.latlng is the mouse position, not the point position -
      // however it helps us know if we have clicked on a point that is wrapped around the world.
      var lat = props.data.lat;
      var lng = props.data.lng;
      if (props.latlng.lng > 180){
        // Tricky because the clicking might not be within the same 360 block at the center of the marker. We must
        // test for this eventuality.
        lng = lng + Math.floor((props.latlng.lng - lng)/360)*360;
        if (props.latlng.lng - lng > 180){
          lng = lng + 360;
        }
      } else if (props.latlng.lng < -180){
        lng = lng - Math.floor((lng - props.latlng.lng)/360)*360;
        if (lng - props.latlng.lng > 180){
          lng = lng - 360;
        }
      }
      // Highlight the point
      this.layers['_point_info_plugin'] = L.circleMarker([lat, lng], {
        radius: 4, /* Ideally the same as the cartoCSS version */
        stroke: true,
        color: '#FFF',
        weight: 1,
        fill: true,
        fillColor: '#00F',
        opacity: 1,
        fillOpacity: 1,
        clickable: false
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
        clickable: false
      });
      this._animate(this.layers['_point_info_plugin_1']);
      // Add the layers in order
      view.map.addLayer(this.layers['_point_info_plugin_1']);
      view.map.addLayer(this.layers['_point_info_plugin']);
      // Add the info in the sidebar
      template_data = $.extend({}, props.data);
      template_data.multiple = options.count_field && props.data[options.count_field] > 1;
      view.sidebar_view.render(template_data, options['template']);
    } else {
      delete this.layers['_point_info_plugin'];
      delete this.layers['_point_info_plugin_1'];
      view.sidebar_view.render(null);
    }
    // Todo: update details tab
  }

  /**
   * Animate
   */
  this._animate = function(layer){
    var plugin = this;
    this.animation = {
      radius: 1,
      fillOpacity: 1,
      drawOpacity: 1
    };
    $(this.animation).animate({
      radius: 20,
      fillOpacity: 0,
      drawOpacity: 0
    }, {
      duration: 750,
      easing: 'swing',
      step: function(value, fx){
        layer.setRadius(this.radius);
        layer.setStyle({fillOpacity: this.fillOpacity});
        layer.setStyle({opacity: this.drawOpacity});
      },
      complete: function(){
        plugin.animation_restart = setTimeout(function(){
          plugin.animation_restart = false;
          $.proxy(plugin, '_animate')(layer);
        }, 1000);
      }
    });
  }

};


/**
 * TooltipPlugin
 *
 * Plugin used to add a tooltip on point hover
 */
my.TooltipPlugin = function(view, options){
  /**
   * enable this plugin
   */
  this.enable = function(){
    this.grid = null;
    this.$el = $('<div>').addClass('map-hover-tooltip').css({
      display: 'none',
      position: 'absolute',
      top: 0,
      left: 0,
      zIndex: 100
    }).appendTo(view.map.getContainer());
    this.hover = false;
  }

  /**
   * Disable this plugin
   */
  this.disable = function(){
    this._disable_event_handlers();
    this.$el.remove();
    this.$el = null;
  }

  /**
   * Remove event handlers
   */
  this._disable_event_handlers = function(){
    if (this.grid){
      this.grid.off('mouseover', $.proxy(this, "_mouseover"));
      this.grid.off('mouseout', $.proxy(this, "_mouseout"));
      view.map.off('mouseout', $.proxy(this, "_mouseout"));
      this.grid = null;
    }
  }

  /**
   * Mouseover handler
   */
  this._mouseover = function(props) {
    var count = options.count_field && props.data[options.count_field] ? props.data[options.count_field] : 1
    var str = false;
    if (options.template && count == 1){
      var template_data = props;
      template_data.multipe = count > 1;
      str = Mustache.render(options.template, props.data);
    } else {
      str = count + ' record' + (count == 1 ? '' : 's');
    }
    if (str){
      this.$el.stop().html(str);
      // Place the element with visibility 'hidden' so we can get it's actual height/width.
      this.$el.css({
        top: 0,
        left: 0,
        visibility: 'hidden',
        display: 'block'
      });
      if (typeof this.initial_opacity === 'undefined'){
        this.initial_opacity = this.$el.css('opacity'); // Store CSS value
        this.$el.css('opacity', 0);
      }
      // Tooltip placement algorithm.
      var point = view.map.latLngToContainerPoint(props.latlng);
      var width = this.$el.width();
      var height = this.$el.height();
      var map_size = view.map.getSize();
      var top, left;
      if (point.x > map_size.x * 4 / 5 || point.x + width + 16 > map_size.x){
        left = point.x - width - 16;
      } else {
        left = point.x + 16;
      }
      if (point.y < map_size.y / 5){
        top = point.y + height * 0.5 + 8;
      } else {
        top = point.y - height * 1.5 - 8;
      }
      this.hover = true;
      this.$el.css({
        top: top,
        left: left,
        visibility: 'visible'
      }).stop().animate({
        opacity: this.initial_opacity
      }, {
        duration: 100
      });
    }
  }

  /**
   * Mouseout handler
   */
  this._mouseout = function(){
    if (this.hover && this.$el){
      this.hover = false;
      this.$el.stop().animate({
        'opacity': 0
      }, {
        duration: 100,
        complete: function(){
          $(this).html('');
          $(this).css('display', 'none');
        }
      });
    }
  }

  /**
   * redraw handler
   */
  this.redraw = function(layers){
    this._disable_event_handlers();
    this.grid = layers['grid'];
    this.grid.on('mouseover', $.proxy(this, "_mouseover"));
    this.grid.on('mouseout', $.proxy(this, "_mouseout"));
    view.map.on('mouseout', $.proxy(this, "_mouseout")); // UtfGrid doesn't trigger mouseout when you leave the map
  }
}

})(jQuery, recline.View);
/**
 * Define the tilemap module
 */
this.ckan.module('tiledmap', function ($) {
  return {
    initialize: function(){
      this.el = $(this.el);
      this.options.resource = JSON.parse(this.options.resource);
      this.options.resource_view = JSON.parse(this.options.resource_view);

      this.el.ready($.proxy(this, '_onReady'));
    },

    _onReady: function(){
      var geom = '';
      var fields = {};
      var q = '';
      if (window.parent.ckan && window.parent.ckan.views.filters){
        var filters = window.parent.ckan.views.filters.get();
        for (var pname in filters){
          if (pname == '_tmgeom'){
            geom = Terraformer.WKT.parse(filters[pname][0]);
          } else {
            fields[pname] = filters[pname][0];
          }
        }
        q = window.parent.ckan.views.filters.getFullText();
      }
      this.view = new (_get_tiledmap_view(this, $))({
        resource_id: this.options.resource.id,
        view_id: this.options.resource_view.id,
        filters: {
          fields: fields,
          geom: geom,
          q: q
        }
      });
      this.view.render();
      $(this.el).append(this.view.el);
      this.view.show();
    }
  };
});

/**
 * NHMMap
 *
 * Custom backbone view to display the Windshaft based maps.
 */
function _get_tiledmap_view(my, $, _){
my.NHMMap = Backbone.View.extend({
  className: 'tiled-map',
  template: '<div class="tiled-map-info"></div><div class="panel sidebar"></div><div class="panel map"></div>',

  /**
   * Initialize
   *
   * This is only called once.
   */
  initialize: function() {
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
  },

  /**
   * Render the map
   *
   * This is called when for the initial map rendering and when the map needs
   * a full refresh (eg. filters are applied).
   */
  render: function() {
    var out = Mustache.render(this.template);
    this.el.html(out);
    this.$map = this.el.find('.panel.map');
    $('.panel.sidebar', this.el).append(this.sidebar_view.el);
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
    var $rri = $('.tiled-map-info', this.el);
    if (this.map_ready){
      if (this.map_info.draw){
          var template = [
            'Displaying <span class="doc-count">{{geoRecordCount}}</span>',
            ' of ',
            '</span><span class="doc-count">{{recordCount}}</span>',
            'records'
          ].join(' ');
          $rri.html(Mustache.render(template, {
            recordCount: this.map_info.total_count ? this.map_info.total_count.toString() : '0',
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
   * Hide the map.
   *
   * This is called when the grid or graph views are selected.
   */
  hide: function() {
     this.el.css('display', 'none');
     this.visible = false
  },

  /**
   * Called when the window is resized to set the map size
   */
  _resize: function(){
    $('div.panel.map, div.panel.sidebar', this.el).height($(window.parent).height()*0.90);
  },

  /**
   * Internal map setup.
   *
   * This is called internally when the map is initially setup, or when it needs
   * a full refresh (eg. filters are applied)
   */
  _setupMap: function(){
    var self = this;
    var bounds = false;
    if (typeof this.map !== 'undefined'){
      bounds = this.map.getBounds();
      this.disablePlugins();
      this.map.remove();
    }
    this.map = new L.Map(this.$map.get(0), {
      worldCopyJump: true
    });
    if (this.map_info.geom_count > 0 || !bounds) {
      bounds = this.map_info.bounds;
    }
    this.map.fitBounds(this.map_info.bounds, {
      animate: false,
      maxZoom: this.map_info.initial_zoom.max
    });
    if (this.map.getZoom() < this.map_info.initial_zoom.min) {
        var center = this.map.getCenter();
        this.map.setView(center, this.map_info.initial_zoom.min)
    }
    L.tileLayer(this.map_info.tile_layer.url, {
        opacity: this.map_info.tile_layer.opacity,
        noWrap: !this.map_info.repeat_map
    }).addTo(this.map);

    this.tilejson = {
            tilejson: '1.0.0',
            scheme: 'xyz',
            tiles: [],
            grids: [],
            formatter: function(options, data) { return 'yo' /*data._id + "/" + data.species + "/" + data.scientific_name*/ }
    };

    this.tiles_url = '/map-tile/{z}/{x}/{y}.png';
    this.grids_url = '/map-grid/{z}/{x}/{y}.grid.json?callback={cb}';

    // Set up the controls available to the map. These are assigned during redraw.
    this.controls = {
      'drawShape': new my.DrawShapeControl(this, this.map_info.control_options['drawShape']),
      'mapType': new my.MapTypeControl(this, this.map_info.control_options['mapType']),
      'fullScreen': new my.FullScreenControl(this, this.map_info.control_options['fullScreen'])
    };

    // Set up the plugins available to the map. These are assigned during redraw.
    this.plugins = {
      'tooltipInfo': new my.TooltipPlugin(this, this.map_info.plugin_options['tooltipInfo']),
      'tooltipCount': new my.TooltipPlugin(this, this.map_info.plugin_options['tooltipCount']),
      'pointInfo': new my.PointInfoPlugin(this, this.map_info.plugin_options['pointInfo'])
    }

    // Setup handling of draw events to ensure plugins work nicely together
    this.map.on('draw:created', function (e) {
      self.setGeom(e.layer.toGeoJSON().geometry);
    });
    this.map.on('draw:drawstart', function(e){
      self.invoke('active', false);
      self.layers['plot'].setOpacity(0.5);
    });
    this.map.on('draw:drawstop', function(e){
      self.invoke('active', true);
      self.layers['plot'].setOpacity(1);
    });
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
        resource_id: this.resource_id,
        view_id: this.view_id,
        fetch_id: this.fetch_count
    };

    var filters = new my.CkanFilterUrl().set_filters(this.filters.fields);
    if (this.filters.geom){
      filters.set_filter('_tmgeom', Terraformer.WKT.convert(this.filters.geom))
    }
    params['filters'] = filters.get_filters();

    if (this.filters.q){
      params['q'] = this.filters.q;
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
   * setGeom
   *
   * Set the geom filter. This will cause the map to be redrawn and links to views to be updated.
   */
  setGeom: function(geom){
    // Get the geometry drawn
    if (!geom && !this.filters.geom){
      return;
    }
    this.filters.geom = geom;
    // Inject the geom search term in links to all other views.
    var param = null;
    if (this.filters.geom){
      param = Terraformer.WKT.convert(this.filters.geom);
    }
    $('section.module ul.view-list li.resource-view-item a', window.parent.document).each(function(){
      var href = new my.CkanFilterUrl($(this).attr('href')).set_filter('_tmgeom', param).get_url();
      $(this).attr('href', href);
    });
    // And redraw the map
    this.redraw();
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
    var filters = new my.CkanFilterUrl().set_filters(this.filters.fields);
    if (this.filters.geom){
      filters.set_filter('_tmgeom', Terraformer.WKT.convert(this.filters.geom))
    }
    params['filters'] = filters.get_filters();

    if (this.filters.q){
      params['q'] = this.filters.q;
    }

    params['resource_id'] = this.resource_id;
    params['view_id'] = this.view_id;
    params['style'] = this.map_info.map_style;

    // Prepare layers
    this.tilejson.tiles = [this.tiles_url + "?" + $.param(params)];
    this.tilejson.grids = [this.grids_url + "&" + $.param(params)];
    for (var i in this.layers){
      this.map.removeLayer(this.layers[i]);
    }
    this._removeAllLayers();
    this._addLayer('selection',  L.geoJson(this.filters.geom));
    this._addLayer('plot', L.tileLayer(this.tilejson.tiles[0], {
      noWrap: !this.map_info.repeat_map
    }));

    var style = this.map_info.map_styles[this.map_info.map_style];
    if (style.has_grid){
      this._addLayer('grid', new L.UtfGrid(this.tilejson.grids[0], {
        resolution: style.grid_resolution,
        pointerCursor: false
      }));
    }
    // Ensure that click events on the selection get passed to the map.
    if (typeof this.layers['selection'] !== 'undefined'){
      this.layers['selection'].on('click', function(e) {
        self.map.fire('click', e);
      });
    }

    // Update controls & plugins
    this.updateControls();
    this.updatePlugins();

    // Add plugin defined layers & call redraw on plugins.
    var extra_layers = this.invoke('layers');
    for (var i in extra_layers){
      this._addLayer(extra_layers[i].name, extra_layers[i].layer);
    }
    this.invoke('redraw', this.layers);
  },

  /**
   * openSidebar
   *
   * Open the sidebar.
   */
  openSidebar: function(){
    var $sb = $('.panel.sidebar', this.el);
    var width = $sb.css('max-width');
      $sb.stop().animate({
        width: width
      }, {
        complete: function(){
          $sb.css('overlow-y', 'auto');
        }
      });
  },

  /**
   * closeSidebar
   *
   * Close the sidebar
   */
  closeSidebar: function(){
    var $sb = $('.panel.sidebar', this.el);
      $sb.stop().animate({
        width: 0
      }, {
        complete: function(){
          $sb.css('overflow-y', 'hidden');
        }
      });
  },

  /**
   * _addLayer
   *
   * This function adds a new layer to the map
   */
  _addLayer: function(name, layer){
    if (typeof this.layers[name] !== 'undefined'){
      this.map.removeLayer(this.layers[name])
    }
    this.layers[name] = layer;
    this.map.addLayer(layer);
  },

  /**
   * _removeLayer
   *
   * This function removes a layer from the map
   */
  _removeLayer: function(name){
    if (typeof this.layers[name] !== 'undefined'){
      this.map.removeLayer(this.layers[name]);
      delete this.layers[name];
    }
  },

  /**
   * _removeAllLayers
   *
   * Removes all layers from the map
   */
  _removeAllLayers: function(){
    for (var i in this.layers){
      this.map.removeLayer(this.layers[i]);
    }
    this.layers = {};
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
   * invoke
   *
   * Invoke a particular hook on enabled plugins and controls
   */
  invoke: function(hook, args){
    var ret = [];
    for (var p in this._current_addons){
      for (var i in this._current_addons[p]){
        var addon = this[p][this._current_addons[p][i]];
        if (typeof addon[hook] == 'function'){
          var lr = addon[hook](args)
          if ($.isArray(lr)){
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
        if (add_cb && $.inArray(addon, this._current_addons[type]) == -1){
          add_cb(addon);
        }
      }
    }
    for (var i in this._current_addons[type]){
      var addon = this._current_addons[type][i];
      if (remove_cb && $.inArray(addon, new_addons) == -1){
        remove_cb(addon);
      }
    }
    this._current_addons[type] = new_addons;
  }
});

/**
 * FullScreenControl
 *
 * Control to make the map fullscreen
 */
my.FullScreenControl = L.Control.Fullscreen.extend({
  initialize: function(view, options) {
    this.view = view;
    L.Util.setOptions(this, options);
    this.is_full_screen = false;
  },

  _onClick: function(e){
    var body = jQuery('body').get(0);
    if (this.is_full_screen) {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      } else if (document.mozCancelFullScreen) {
        document.mozCancelFullScreen();
      } else if (document.webkitCancelFullScreen) {
        document.webkitCancelFullScreen();
      } else if (document.msExitFullscreen) {
        document.msExitFullscreen();
      }
      $(body).removeClass('fullscreen');
    } else {
      //FIXME: Handle older browsers
      if (body.requestFullscreen) {
          body.requestFullscreen();
      } else if (body.mozRequestFullScreen) {
          body.mozRequestFullScreen();
      } else if (body.webkitRequestFullscreen) {
          body.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT);
      } else if (body.msRequestFullscreen) {
        body.msRequestFullscreen();
      }
      $(body).addClass('fullscreen');
    }
    this.is_full_screen = !this.is_full_screen;
    e.stopPropagation();
    return false;
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
     var $elem = $('<a></a>').attr('href', '#').attr('title', 'full screen').html('F').appendTo(this.$bar)
     .click($.proxy(this, '_onClick'));
     return L.DomUtil.get(this.$bar.get(0));
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
 * Extend draw shape control to add country selection support and a way to clear the current selection.
 */
my.DrawShapeControl = L.Control.Draw.extend({
  initialize: function(view, options) {
      this.view = view;
      this.active = false;
      L.Control.Draw.prototype.initialize.call(this, options);
      L.Util.setOptions(this, options);
      // Pre-emptively load country data
      this._loadCountries();
  },

  onAdd: function(map){
    var self = this;
    // Call base Draw onAdd
    var elem = L.Control.Draw.prototype.onAdd.call(this, map);
    // Add the select country action
    $('<a></a>').attr('href', '#').attr('title', 'Select by country').html('C').css({
      'background-image': 'none'
    }).appendTo($('div.leaflet-bar', elem))
      .click($.proxy(this, 'onCountrySelectionClick'));
    // Ensure the country select action stops when another draw is started
    map.on('draw:drawstart', function(e){
      if (self.active && e.layerType != 'country'){
        self.active = false;
        self._disactivate();
      }
    });
    // Add the clear selection action
    $('<a></a>').attr('href', '#').attr('title', 'Clear selection').addClass('leaflet-draw-edit-remove')
      .appendTo($('div.leaflet-bar', elem))
      .click(function(e){
        self.view.setGeom(null);
        e.stopPropagation();
        return false;
      });

    return elem;
  },

  /**
   * _loadCountries
   *
   * Internal method to load the countries data
   */
  _loadCountries: function(){
    $.ajax('/data/countries.geojson', {
      dataType: 'json',
      error: function(xhr, status, error){
        console.log('failed to load countries');
      },
      success: $.proxy(function(data, status, xhr){
        this.countries = data;
      }, this)
    });
  },

  /**
   * layers
   *
   * Plugin hook called when adding layers to a map.
   */
  layers: function(){
    var self = this;
    if (!this.active || !this.countries){
      return [];
    }
    // The main layer is used only for hovers
    var l = new L.geoJson(this.countries, {
      style: function(){
        return {
          stroke: true,
          color: '#000',
          opacity: 1,
          weight: 1,
          fill: true,
          fillColor: '#FFF',
          fillOpacity: 0.25
        };
      },
      onEachFeature: function(feature, layer){
        layer.on({
          mouseover: function(e){
            layer.setStyle({
              stroke: true,
              color: '#000',
              opacity: 1,
              weight: 1,
              fill: true,
              fillColor: '#54F',
              fillOpacity: 0.75
            });
          },
          mouseout: function(e){
            layer.setStyle({
              stroke: true,
              color: '#000',
              opacity: 1,
              weight: 1,
              fill: true,
              fillColor: '#FFF',
              fillOpacity: 0.25
            });
          },
          click: function(e){
            self.view.map.fire('draw:created', {
              layer: layer,
              layerType: 'country'
            });
            self._disactivate();
          }
        })
      }
    });
    return [{'name': 'countries', 'layer': l}];
  },

  _activate: function(){
    // Add the layer
    var l = this.layers();
    this.view._addLayer('countries', l[0].layer, true);
    // Add action
    var action_inner = $('<a>').attr('href', '#').html('Cancel').click($.proxy(this, 'onCountrySelectionClick'));
    this.action = $('<li>').append(action_inner);
    $('ul.leaflet-draw-actions').empty().append(this.action).css({
      display: 'block',
      top: '52px'
    });
    // Ensure plugins can react to this
    this.view.map.fireEvent('draw:drawstart', {layerType: 'country'});
  },

  _disactivate: function(){
    // Remove layer
    this.view._removeLayer('countries', true);
    // Hide actions
    this.action.remove();
    $('ul.leaflet-draw-actions').css('display', 'none');
    // Ensure plugins can react to this
    this.view.map.fireEvent('draw:drawstop', {'layerType': 'country'});
  },

  onCountrySelectionClick: function(e){
    this.active = !this.active;
    if (this.active){
      this._activate();
    }else{
      this._disactivate();
    }
    e.stopPropagation();
    return false;
  }
});

/**
 * Recline sidebar view for map point information
 */
my.PointDetailView = Backbone.View.extend({
  className: 'tiled-map-point-detail',
  template: '<div class="tiled-map-point-detail"></div>',
  initialize: function() {
    this.el = $(this.el);
    this.render();
    this.has_content = false;
  },
  render: function(data, template) {
    var self = this;
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
    if (this.has_content) {
      this.el.stop().animate({
        opacity: 0
      }, {
        duration: 200,
        complete: function () {
          self.el.html(out);
          self.el.animate({opacity: 1}, {duration: 200});
        }
      });
    } else {
      self.el.html(out);
      this.el.stop().animate({opacity: 1}, {duration: 200});
    }
    this.has_content = data ? true : false;
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
    this.isactive = true;
  }

  /**
   * Disable this plugin
   */
  this.disable = function(){
    // remove handlers
    this._disable_event_handlers();
  }

  /**
   * Activate/disactive this plugin
   * (Used for temporary pause)
   */
  this.active = function(state){
    this.isactive = state;
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
    if (!this.isactive){return;}
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
    if (props && props.data && (view.map_info.repeat_map || (props.latlng.lng >= -180 && props.latlng.lng <= 180))){
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
      template_data = $.extend({
        _resource_url: window.parent.location.pathname,
        _multiple: options.count_field && props.data[options.count_field] > 1
      }, props.data);
      if (window.parent.ckan && window.parent.ckan.views.filters && props.data.grid_bbox){
        var filters = window.parent.ckan.views.filters.get();
        var furl = new my.CkanFilterUrl().set_filters(filters);
        furl.add_filter('_tmgeom', props.data.grid_bbox);
        template_data._overlapping_records_filters = encodeURIComponent(furl.get_filters());
      }
      view.sidebar_view.render(template_data, options['template']);
      view.openSidebar();
    } else {
      delete this.layers['_point_info_plugin'];
      delete this.layers['_point_info_plugin_1'];
      view.sidebar_view.render(null);
      view.closeSidebar();
    }
  }

  /**
   * Animate
   */
  this._animate = function(layer){
    var plugin = this;
    this.animation = {
      radius: 1,
      fillOpacity: 1,
      drawOpacity: 1,
      style: {} // Some jQuery versions require this.
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
    this.isactive = true;
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
   * Activate/disactive this plugin
   * (Used for temporary pause)
   */
  this.active = function(state){
    this.isactive = state;
  }

  /**
   * Mouseover handler
   */
  this._mouseover = function(props) {
    if (!this.isactive){return;}
    if (props && props.data && !view.map_info.repeat_map && (props.latlng.lng < -180 || props.latlng.lng > 180)){
      return;
    }
    var count = options.count_field && props.data[options.count_field] ? props.data[options.count_field] : 1
    var str = false;
    if (options.template && count == 1){
      var template_data = $.extend({
        _multiple: count > 1,
        _resource_url: window.parent.location.pathname
      }, props);
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
    // Set the mouse cursor.
    $('div.panel.map').css('cursor', 'pointer');
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
      // Remove the mouse cursor
      $('div.panel.map').css('cursor', '');
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

/**
 * CKanFilterUrl
 *
 * Class used to parse and create URLs with a query string parameter 'filter' build as 'name:value|....'
 */
my.CkanFilterUrl = function(input_url){
  /**
   * initialize
   *
   * Set up the object
   */
  this.initialize = function(){
    if (typeof input_url !== 'undefined'){
      this.set_url(input_url);
    } else {
      this.base = '';
      this.qs = {};
    }
  }

  /**
   * set_url
   *
   * Set this object's URL
   */
  this.set_url = function(url){
    var parts = url.split('?');
    this.base = parts[0];
    this.qs = {};
    if (parts.length > 1){
      var qs_idx = parts[1].split('&');
      for (var i in qs_idx){
        var p = qs_idx[i].split('=');
        p[0] = decodeURIComponent(p[0]);
        p[1] = decodeURIComponent(p[1]);
        this.qs[p[0]] = p[1]
      }
      if (typeof this.qs['filters'] !== 'undefined'){
        this.set_filters(this.qs['filters']);
      }
    }

    return this;
  }

  /**
   * add_filter
   *
   * Add a filter to the current URL.
   */
  this.add_filter = function(name, value){
    if (typeof this.qs['filters'] === 'undefined'){
      this.qs['filters'] = {};
    }
    if ($.isArray(value)){
      // TODO: check how ckan handles multivalued.
      this.qs['filters'][name] = value.join('');
    } else {
      this.qs['filters'][name] = value;
    }

    return this;
  }

  /**
   * remove_filter
   *
   * Remove filter from the current url
   */
  this.remove_filter = function(name){
    if (typeof this.qs['filters'] !== 'undefined'){
      delete this.qs['filters'][name];
      if ($.isEmptyObject(this.qs['filters'])){
        delete this.qs['filters'];
      }
    }
    return this;
  }

  /**
   * set_filter
   *
   * Set a filter value on the URL. If the value evaluates to false, the filter is removed
   */
  this.set_filter = function(name, value){
    if (!value){
      this.remove_filter(name);
    } else {
      this.add_filter(name, value);
    }

    return this;
  }

  /**
   * set_filters
   *
   * Set the filters of the URL. The value may be a decoded query string formated filter (a:b|...), or a dictionary
   * of name to value.
   */
  this.set_filters = function(filters){
    delete this.qs['filters'];
    if (typeof filters == 'string' && filters){
      var split = filters.split('|');
      for (var i in split){
        var parts = split[i].split(':');
        if (parts.length == 2){
          this.set_filter(parts[0], parts[1])
        }
      }
    } else if (typeof filters == 'object'){
      for (var i in filters){
        this.set_filter(i, filters[i])
      }
    }
    return this;
  }

  /**
   * get_filters
   *
   * Returns the filter query string alone (not encoded)
   */
  this.get_filters = function(){
    if (typeof this.qs['filters'] === 'undefined'){
      return '';
    }
    var b_filter = [];
    for (var f in this.qs['filters']){
      b_filter.push(f + ':' + this.qs['filters'][f])
    }
    return b_filter.join('|')
  }

  /**
   * get_url
   *
   * Return the URL as a string
   */
  this.get_url = function(){
    var b_qs = [];
    for (var i in this.qs){
      var val;
      if (i == 'filters'){
        val = this.get_filters();
      } else {
        val = this.qs[i];
      }
      b_qs.push(encodeURIComponent(i) + '=' + encodeURIComponent(val));
    }

    return this.base + '?' + b_qs.join('&');
  }

  this.initialize();
}

return my.NHMMap;
}
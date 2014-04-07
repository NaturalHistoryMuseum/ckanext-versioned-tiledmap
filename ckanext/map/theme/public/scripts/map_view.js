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
  className: 'recline-nhm-map well',
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

    this.drawLayer = null;

    this.tilejson = {
            tilejson: '1.0.0',
            scheme: 'xyz',
            tiles: [],
            grids: [],
            formatter: function(options, data) { return data._id + "/" + data.species + "/" + data.scientific_name }
    };

    this.map.on('draw:created', function (e) {
      // Set the the geometry in the queryState to persist it between filter/search updates
      self.model.queryState.attributes.geom = e.layer.toGeoJSON().geometry;
      self.redraw();
    });

    this.tiles_url = '/map-tile/{z}/{x}/{y}.png';
    this.grids_url = '/map-grid/{z}/{x}/{y}.grid.json?callback={cb}';

    // Set up the controls used by the map. These are assigned during redraw.
    this.controls = {
      'drawShape': new my.DrawShapeControl(this, this.map_info.control_options['drawShape']),
      'mapType': new my.MapTypeControl(this, this.map_info.control_options['mapType']),
      'pointInfo': new my.PointInfoControl(this, this.map_info.control_options['pointInfo']),
      'gridInfo': new my.GridInfoControl(this, this.map_info.control_options['gridInfo'])
    }

    this.layers = [];
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
    var params = {};

    if (!this.map_ready || !this.map_info.draw){
      return;
    }

    if (self.drawLayer) {
      self.map.removeLayer(self.drawLayer);
    }

    self.drawLayer = L.geoJson(this.model.queryState.attributes.geom);
    self.map.addLayer(self.drawLayer);

    params['filters'] = JSON.stringify(this.model.queryState.attributes.filters);

    if (this.model.queryState.attributes.q){
      params['q'] = this.model.queryState.attributes.q;
    }

    if (this.model.queryState.attributes.geom) {
      params['geom'] = Terraformer.WKT.convert(this.model.queryState.attributes.geom);
    }

    params['resource_id'] = this.model.id;
    params['style'] = this.map_info.map_style;

    this.tilejson.tiles = [this.tiles_url + "?" + $.param(params)];
    this.tilejson.grids = [this.grids_url + "&" + $.param(params)];

    _.each(this.layers, function(layer){
        self.map.removeLayer(layer)
    });

    this.layers = [];

    var testMap = L.tileLayer(this.tilejson.tiles[0]).addTo(this.map);
    this.layers.push(testMap);

    // Update controls
    var grid_controls = [];
    if (typeof this._current_controls === 'undefined'){
      this._current_controls = [];
    }
    var new_controls = [];
    for (var i in this.map_info.map_styles[this.map_info.map_style].controls){
      var control = this.map_info.map_styles[this.map_info.map_style].controls[i];
      new_controls.push(control);
      if (!_.contains(this._current_controls, control)){
        this.map.addControl(this.controls[control]);
      }
      if (typeof this.controls[control].setGrid !== 'undefined'){
        grid_controls.push(this.controls[control]);
      }
    }
    for (var i in this._current_controls){
      var control = this._current_controls[i];
      if (!_.contains(new_controls, control)){
        this.map.removeControl(this.controls[control]);
      }
    }
    this._current_controls = new_controls;

    // Add the grid layer. We only need it if we have a control that subscribes to it.
    if (grid_controls.length > 0) {
      var utfGrid = new L.UtfGrid(this.tilejson.grids[0], {
        resolution: 4,
      });

      this.map.addLayer(utfGrid);
      this.layers.push(utfGrid);
      for (var i in grid_controls){
        grid_controls[i].setGrid(utfGrid)
      }
    }
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
 * PointInfoControl
 *
 * Custom control to display info about specific map points
 * (used for plot maps only).
 *
 */
my.PointInfoControl = L.Control.extend({
    initialize: function(view, options) {
        this.view = view;
        L.Util.setOptions(this, options);
    },

    onAdd: function(map){
      this._div = L.DomUtil.create('div', 'info'); // create a div with a class "info"
      this.pointOut();
      return this._div;
    },

    pointOut: function(){
      var template = [
        '<h4>' + this.view.model.attributes.name + ' Records</h4>',
        '<p>Hover over a marker</p>'
      ].join('');
      this._div.innerHTML = Mustache.render(template);
    },

    pointOver: function(props){
      var template = [
        '<h4>' + this.view.model.attributes.name + ' Records</h4>',
        '<b>{{ data.species }}</b><br />',
        '{{ data._id }}<br />',
        '{{ data.scientific_name }}<br/>',
        '{{ data.count }} records overlapping'
      ].join('');
      this._div.innerHTML = Mustache.render(template, props);
    },

    setGrid: function(grid){
      grid.on('mouseover', $.proxy(this, 'pointOver'));
      grid.on('mouseout', $.proxy(this, 'pointOut'));
    }
});

/**
 * GridInfoControl
 *
 * Custom control to display info about specific grid sections
 * (used for grid maps only).
 *
 */
my.GridInfoControl = L.Control.extend({
    initialize: function(view, options) {
        this.view = view;
        L.Util.setOptions(this, options);
    },

    onAdd: function(map){
      this._div = L.DomUtil.create('div', 'small-info'); // create a div with a class "small-info"
      return this._div;
    },

    setGrid: function(grid){
      grid.on('mouseover', $.proxy(function(props){
        var template = [
          '{{ data.count }} records'
        ].join('');
        this._div.innerHTML = Mustache.render(template, props);
      }, this));
      grid.on('mouseout', $.proxy(function(){
        this._div.innerHTML = '';
      }, this));
    }
});

})(jQuery, recline.View);
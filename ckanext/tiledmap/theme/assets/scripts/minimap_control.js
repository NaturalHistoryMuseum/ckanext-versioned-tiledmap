this.tiledmap = this.tiledmap || {};

(function (my, $) {
  var self;
  /**
   * Extend minimap control to add custom viewport
   */
  my.MiniMapControl = L.Control.MiniMap.extend({
    initialize: function (view, options) {
      self = this;
      options.aimingRectOptions = { stroke: false, fill: false };
      options.shadowRectOptions = { stroke: false, fill: false };
      self._viewport_type = 'none';
      self._tile_layer = L.tileLayer(options.tile_layer.url);
      L.Control.MiniMap.prototype.initialize.call(
        self,
        self._tile_layer,
        options,
      );
    },

    onAdd: function (map) {
      var pret = L.Control.MiniMap.prototype.onAdd.call(self, map);
      self._map = map;
      self._viewports = {
        rect: L.rectangle(self._map.getBounds(), self.options.viewport.rect),
        marker: new L.CircleMarker(
          self._map.getCenter(),
          self.options.viewport.marker,
        ),
      };
      self._miniMap.whenReady(function () {
        self.updateViewport();
        self._miniMap.on('move', self.updateViewport);
        self._map.on('move', self.updateViewport);
        self._setDisplay(self._decideMinimized());
      });
      return pret;
    },

    updateViewport: function () {
      var viewport_type;
      if (!self._miniMap.getBounds().contains(self._map.getBounds())) {
        viewport_type = 'none';
      } else {
        if (self._map.getZoom() >= self.options.viewport.marker_zoom) {
          viewport_type = 'marker';
        } else {
          viewport_type = 'rect';
        }
      }
      // Add the viewport to the minimap if needed
      if (viewport_type !== self._viewport_type) {
        if (typeof self._viewports[self._viewport_type] !== 'undefined') {
          self._miniMap.removeLayer(self._viewports[self._viewport_type]);
        }
        if (typeof self._viewports[viewport_type] !== 'undefined') {
          self._viewports[viewport_type].addTo(self._miniMap);
        }
        self._viewport_type = viewport_type;
      }
      // Update bounds/position of viewport
      if (self._viewport_type === 'rect') {
        self._viewports['rect'].setBounds(self._map.getBounds());
        self._viewports['rect'].redraw();
      } else if (self._viewport_type === 'marker') {
        self._viewports['marker'].setLatLng(self._map.getCenter());
        self._viewports['marker'].redraw();
      }
    },
  });
})(this.tiledmap, jQuery);

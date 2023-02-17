this.tiledmap = this.tiledmap || {};

(function (my, $) {
  /**
   * Extend draw shape control to add country selection support and a way to clear the current selection.
   */
  my.DrawShapeControl = L.Control.Draw.extend({
    initialize: function (view, options) {
      this.view = view;
      this.active = false;
      this.country = options.draw.country;
      L.Control.Draw.prototype.initialize.call(this, options);
      L.Util.setOptions(this, options);
      if (this.country) {
        this._loadCountries();
      }
    },

    onAdd: function (map) {
      var self = this;
      // Call base Draw onAdd
      var elem = L.Control.Draw.prototype.onAdd.call(this, map);
      // Add the select country action
      if (this.country) {
        $('<a></a>')
          .attr('href', '#')
          .attr('title', 'Select by country')
          .addClass('leaflet-draw-draw-country')
          .appendTo($('div.leaflet-bar', elem))
          .click($.proxy(this, 'onCountrySelectionClick'));
        // Ensure the country select action stops when another draw is started
        map.on('draw:drawstart', function (e) {
          if (self.active && e.layerType !== 'country') {
            self.active = false;
            self._disactivate();
          }
        });
      }
      // Add the clear selection action
      $('<a></a>')
        .attr('href', '#')
        .attr('title', 'Clear selection')
        .addClass('leaflet-draw-edit-remove')
        .appendTo($('div.leaflet-bar', elem))
        .click(function (e) {
          self.view.setGeom(null);
          e.stopPropagation();
          return false;
        });

      return elem;
    },

    /**
     * Internal method to load the countries data
     */
    _loadCountries: function () {
      $.ajax('/data/countries.geojson', {
        dataType: 'json',
        error: function (xhr, status, error) {
          console.log('failed to load countries');
        },
        success: $.proxy(function (data, status, xhr) {
          this.countries = data;
        }, this),
      });
    },

    /**
     * Plugin hook called when adding layers to a map.
     */
    layers: function () {
      var self = this;
      if (!this.active || !this.countries) {
        return [];
      }
      // The main layer is used only for hovers
      var l = new L.geoJson(this.countries, {
        style: function () {
          return {
            stroke: true,
            color: '#000',
            opacity: 1,
            weight: 1,
            fill: true,
            fillColor: '#FFF',
            fillOpacity: 0.25,
          };
        },
        onEachFeature: function (feature, layer) {
          layer.on({
            mouseover: function (e) {
              layer.setStyle({
                stroke: true,
                color: '#000',
                opacity: 1,
                weight: 1,
                fill: true,
                fillColor: '#54F',
                fillOpacity: 0.75,
              });
            },
            mouseout: function (e) {
              layer.setStyle({
                stroke: true,
                color: '#000',
                opacity: 1,
                weight: 1,
                fill: true,
                fillColor: '#FFF',
                fillOpacity: 0.25,
              });
            },
            click: function (e) {
              self.view.map.fire('draw:created', {
                layer: layer,
                layerType: 'country',
              });
              self._disactivate();
            },
          });
        },
      });
      return [{ name: 'countries', layer: l }];
    },

    _activate: function () {
      // Add the layer
      var l = this.layers();
      this.view._addLayer('countries', l[0].layer, true);
      // Add action
      var action_inner = $('<a>')
        .attr('href', '#')
        .html('Cancel')
        .click($.proxy(this, 'onCountrySelectionClick'));
      this.action = $('<li>').append(action_inner);
      $('ul.leaflet-draw-actions').empty().append(this.action).css({
        display: 'block',
        top: '52px',
      });
      // Ensure plugins can react to this
      this.view.map.fireEvent('draw:drawstart', { layerType: 'country' });
    },

    _disactivate: function () {
      // Remove layer
      this.view._removeLayer('countries', true);
      // Hide actions
      this.action.remove();
      $('ul.leaflet-draw-actions').css('display', 'none');
      // Ensure plugins can react to this
      this.view.map.fireEvent('draw:drawstop', { layerType: 'country' });
    },

    onCountrySelectionClick: function (e) {
      this.active = !this.active;
      if (this.active) {
        this._activate();
      } else {
        this._disactivate();
      }
      e.stopPropagation();
      return false;
    },
  });
})(this.tiledmap, jQuery);

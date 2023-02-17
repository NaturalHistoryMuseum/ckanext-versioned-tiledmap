this.tiledmap = this.tiledmap || {};

(function (my, $) {
  /**
   * Custom control interface for Leaflet allowing users to switch between map styles.
   */
  my.MapTypeControl = L.Control.extend({
    initialize: function (view, options) {
      this.view = view;
      L.Util.setOptions(this, options);
    },

    getItemClickHandler: function (style) {
      return $.proxy(function (e) {
        var $active = $('a.active-selection', this.$bar);
        if ($active.length > 0 && $active.attr('stylecontrol') === style) {
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

    onAdd: function (map) {
      this.$bar = $('<div>').addClass('leaflet-bar');
      for (var style in this.view.map_info.map_styles) {
        var title = this.view.map_info.map_styles[style].name;
        var icon = this.view.map_info.map_styles[style].icon;
        var $elem = $('<a></a>')
          .attr('href', '#')
          .attr('title', title)
          .html(icon)
          .attr('stylecontrol', style)
          .appendTo(this.$bar)
          .click(this.getItemClickHandler(style));
        if (style === this.view.map_info.map_style) {
          $elem.addClass('active-selection');
        }
      }
      return L.DomUtil.get(this.$bar.get(0));
    },
  });
})(this.tiledmap, jQuery);

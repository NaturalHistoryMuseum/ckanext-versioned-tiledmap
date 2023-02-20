this.tiledmap = this.tiledmap || {};

(function (my, $) {
  /**
   * Control to make the map fullscreen
   */
  my.FullScreenControl = L.Control.extend({
    initialize: function (view, options) {
      this.view = view;
      L.Util.setOptions(this, options);
      this.is_full_screen = false;
    },

    _onClick: function (e) {
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
      var body = jQuery('body').get(0);
      this.$bar = $('<div>').addClass('leaflet-bar');
      if (
        body.requestFullscreen ||
        body.mozRequestFullScreen ||
        body.webkitRequestFullscreen
      ) {
        $('<a></a>')
          .attr('href', '#')
          .attr('title', 'full screen')
          .html('<i class="fa fa-expand"></i>')
          .appendTo(this.$bar)
          .click($.proxy(this, '_onClick'));
      }

      return L.DomUtil.get(this.$bar.get(0));
    },
  });
})(this.tiledmap, jQuery);

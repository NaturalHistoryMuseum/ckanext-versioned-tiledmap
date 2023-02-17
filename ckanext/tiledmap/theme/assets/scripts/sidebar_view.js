this.tiledmap = this.tiledmap || {};

(function (my, $) {
  /**
   * Recline sidebar view for map point information
   */
  my.PointDetailView = Backbone.View.extend({
    className: 'tiled-map-point-detail',
    template: '<div class="tiled-map-point-detail"></div>',
    initialize: function () {
      this.el = $(this.el);
      this.render();
      this.has_content = false;
    },
    render: function (data, template) {
      var self = this;
      var out = '';
      if (!data) {
        out = Mustache.render(this.template);
      } else if (data && !template) {
        for (var i in data) {
          out = i.toString() + ': ' + data.toString() + '<br/>';
        }
      } else {
        out = Mustache.render(template, data);
      }
      if (this.has_content) {
        this.el.stop().animate(
          {
            opacity: 0,
          },
          {
            duration: 200,
            complete: function () {
              self.el.html(out);
              self.el.animate({ opacity: 1 }, { duration: 200 });
            },
          },
        );
      } else {
        self.el.html(out);
        this.el.stop().animate({ opacity: 1 }, { duration: 200 });
      }
      this.has_content = !!data;
    },
  });
})(this.tiledmap, jQuery);

this.tiledmap = this.tiledmap || {};
/**
 * Define the tiledmap module
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
          if (pname == '__geo__') {
            geom = JSON.parse(filters[pname][0]);
          } else {
            fields[pname] = filters[pname][0];
          }
        }
        q = window.parent.ckan.views.filters.getFullText();
      }
      this.view = new tiledmap.NHMMap({
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
this.tiledmap = this.tiledmap || {};

/**
 * Define the tiledmap module
 */
this.ckan.module('tiledmap', function ($) {
  return {
    initialize: function () {
      this.el = $(this.el);
      this.options.resource = JSON.parse(this.options.resource);
      this.options.resource_view = JSON.parse(this.options.resource_view);

      this.el.ready($.proxy(this, '_onReady'));
    },

    _onReady: function () {
      setTimeout(this.waitForViews.bind(this, 0), 0);
    },

    /**
     * This module relies on the existence of window.parent.ckan.views and
     * window.parent.ckan.views.filters to operate properly and therefore we need to wait for those
     * properties to become available. This function does just that, checking on a timeout loop
     * every 50ms to see if the properties exist before calling the loadView function. If we attempt
     * this check 100 or more times (more than 5 seconds) we give up and let the view load anyway.
     *
     * Sometimes this module loads before those properties are defined and therefore this module
     * fails due to the race condition. This only happens/is far more likely to happen when used in
     * an iframe where window.parent actually points to the parent rather than window.
     *
     * @param attempts the number of attempts at checking for the properties that we've done
     */
    waitForViews: function (attempts) {
      if (
        (window.parent.ckan &&
          window.parent.ckan.views &&
          window.parent.ckan.views.filters) ||
        attempts >= 100
      ) {
        // the properties exist or we've waited for 2 seconds, let's go!
        this.loadView();
      } else {
        // the properties aren't there yet, wait 50ms and try again
        setTimeout(this.waitForViews.bind(this, attempts + 1), 50);
      }
    },

    loadView: function () {
      var geom = '';
      var fields = {};
      var q = '';
      if (window.parent.ckan && window.parent.ckan.views.filters) {
        var filters = window.parent.ckan.views.filters.get();
        for (var pname in filters) {
          if (pname === '__geo__') {
            geom = JSON.parse(filters[pname][0]);
          } else {
            fields[pname] = filters[pname][0];
          }
        }
        q = window.parent.ckan.views.filters._searchParams.q;
      }
      this.view = new tiledmap.NHMMap({
        resource_id: this.options.resource.id,
        view_id: this.options.resource_view.id,
        filters: {
          fields: fields,
          geom: geom,
          q: q,
        },
      });
      this.view.render();
      $(this.el).append(this.view.el);
      this.view.show();
    },
  };
});

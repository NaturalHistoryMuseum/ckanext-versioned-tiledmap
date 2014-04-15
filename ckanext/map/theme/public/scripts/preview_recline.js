/* Custom recline preview module ; provides:
 *
 *  - Clickabed IDs
 *  - Windshaft map (ckanext-map extention)
 *
 * This gets loaded through the data-module declaration in recline.html.
 * Note that this does not prevent the origin preview_recline.js from being included ;
 * but this one gets executed.
 */
this.ckan.module('nhm-reclinepreview', function (jQuery, _) {

  /**
   * Tabbed view for sidebar
   */
  var TabbedView = Backbone.View.extend({
    template: [
      '<div class="tabview">',
        '<div class="tabview-navigation" data-toggle="tab">',
          '{{#views}}',
          '<a href="#{{id}}" data-view="{{id}}" class="tab">{{label}}</a>',
          '{{/views}}',
        '</div>',
        '<div class="tabview-container"></div>',
      '</div>'
    ].join("\n"),
    events: {
      'click .tabview-navigation a': '_onSwitchTab'
    },
    initialize: function(options) {
      this.el = $(this.el); // Ckan expects this
      this.views = options.views;
      this.render();
      if (options.default){
        this.selectTab(options.default);
      } else if (this.views.length > 0) {
        this.selectTab(this.views[0].id);
      }
    },
    render: function() {
      var template = Mustache.render(this.template, {views: this.views});
      this.el.html(template);

      // now create and append other views
      var $dataViewContainer = this.el.find('.tabview-container');
      for (var i in this.views){
        this.views[i].view.render();
        $dataViewContainer.append(this.views[i].view.el)
      }

      // Reset the current tab
      this.current_tab = false;
    },
    _onSwitchTab: function(e) {
      e.preventDefault();
      var view_name = $(e.target).attr('data-view');
      this.selectTab(view_name);
    },
    selectTab: function(view_name) {
      if (this.current_tab == view_name){
        return;
      }
      this.current_tab = view_name;
      this.el.find('.tabview-navigation a').removeClass('tabview-active');
      var $el = this.el.find('.tabview-navigation a[data-view="' + view_name+ '"]');
      $el.addClass('tabview-active');

      // Show/hide relevant views.
      for (var i in this.views){
        var view = this.views[i];
        if (view.id === view_name){
          // User 'display' property rather than calling show/hide as the latter only look at element properties,
          // not CSS classes (some views are hidden by default in CSS).
          $(view.view.el).css('display', 'block');
        } else {
          $(view.view.el).css('display', 'none');
        }
      }
    },
    enableTabs: function(tabs){
      if (tabs.length > 0){
        if ($.inArray(this.current_tab, tabs) == -1){
          this.selectTab(tabs[0]);
        }
      }
      this.el.find('.tabview-navigation a').css('display', 'none');
      for (var i in tabs){
        this.el.find('.tabview-navigation a[data-view="' + tabs[i] + '"]').css('display', 'block');
      }
    }
  });

  /**
   * The module definition
   */
  return {
    options: {
      i18n: {
        errorLoadingPreview: "Could not load preview",
        errorDataProxy: "DataProxy returned an error",
        errorDataStore: "DataStore returned an error",
        previewNotAvailableForDataType: "Preview not available for data type: "
      },
      site_url: ""
    },

    initialize: function () {
      jQuery.proxyAll(this, /_on/);
      this.el.ready(this._onReady);
      // hack to make leaflet use a particular location to look for images
      L.Icon.Default.imagePath = this.options.site_url + 'vendor/leaflet/0.4.4/images';
    },

    _onReady: function() {
      this.loadPreviewDialog(preload_resource);
    },

    // **Public: Loads a data preview**
    //
    // Fetches the preview data object from the link provided and loads the
    // parsed data from the webstore displaying it in the most appropriate
    // manner.
    //
    // link - Preview button.
    //
    // Returns nothing.
    loadPreviewDialog: function (resourceData) {

      var self = this;

      function showError(msg){
        msg = msg || _('error loading preview');
        window.parent.ckan.pubsub.publish('data-viewer-error', msg);
      }

      recline.Backend.DataProxy.timeout = 10000;
      // will no be necessary any more with https://github.com/okfn/recline/pull/345
      recline.Backend.DataProxy.dataproxy_url = '//jsonpdataproxy.appspot.com';

      // 2 situations
      // a) something was posted to the datastore - need to check for this
      // b) csv or xls (but not datastore)
      resourceData.formatNormalized = this.normalizeFormat(resourceData.format);

      resourceData.url  = this.normalizeUrl(resourceData.url);
      if (resourceData.formatNormalized === '') {
        var tmp = resourceData.url.split('/');
        tmp = tmp[tmp.length - 1];
        tmp = tmp.split('?'); // query strings
        tmp = tmp[0];
        var ext = tmp.split('.');
        if (ext.length > 1) {
          resourceData.formatNormalized = ext[ext.length-1];
        }
      }

      var errorMsg, dataset;

      if (resourceData.datastore_active) {

        resourceData.backend =  'ckan';
        // Set endpoint of the resource to the datastore api (so it can locate
        // CKAN DataStore)
        resourceData.endpoint = jQuery('body').data('site-root') + 'api';

        dataset = new recline.Model.Dataset(resourceData);
        errorMsg = this.options.i18n.errorLoadingPreview + ': ' + this.options.i18n.errorDataStore;
        dataset.fetch()
          .done(function(dataset){
              self.initializeDataExplorer(dataset);
          })
          .fail(function(error){
            if (error.message) errorMsg += ' (' + error.message + ')';
            showError(errorMsg);
          });

      } else if (resourceData.formatNormalized in {'csv': '', 'xls': ''}) {
        // set format as this is used by Recline in setting format for DataProxy
        resourceData.format = resourceData.formatNormalized;
        resourceData.backend = 'dataproxy';
        dataset = new recline.Model.Dataset(resourceData);
        errorMsg = this.options.i18n.errorLoadingPreview + ': ' +this.options.i18n.errorDataProxy;
        dataset.fetch()
          .done(function(dataset){
            dataset.bind('query:fail', function (error) {
              jQuery('.data-view-container', self.el).hide();
              jQuery('.header', self.el).hide();
            });

            self.initializeDataExplorer(dataset);
          })
          .fail(function(error){
            if (error.message) errorMsg += ' (' + error.message + ')';
            showError(errorMsg);
          });
      }
    },

    initializeDataExplorer: function (dataset) {

      dataset.fields.models[0].renderer = function(value, field, record){

          if(field.id == '_id'){

              // Only set if this is an integer - this seems to get called twice
              // TODO: Investigate why...
              if (!isNaN(value)){
                value = '<a href="record/'+ value + '" target="_parent">View record</a>';
              }
              return value

          }

      };

      var views = {
        grid: {
          id: 'grid',
          label: 'Grid',
          view: new recline.View.SlickGrid({
            model: dataset
          }),
          tabs: ['valueFilter']
        },
        graph:  {
          id: 'graph',
          label: 'Graph',
          view: new recline.View.Graph({
            model: dataset
          }),
          tabs: ['valueFilter', 'graphControl'],
          activate_tab: 'graphControl'
        },
        map: {
          id: 'map',
          label: 'Map',
          view: new recline.View.NHMMap({
            model: dataset
          }),
          tabs: ['valueFilter', 'pointDetail'],
          activate_tab: 'pointDetail'
        }
      };
      var flat_views = $.map(views, function(v,k){return v;});

      /* We skip recline's sidebar views; instead we create a single tabbed view that we set as non-optional sidebar
         element for all the views in the multi-view. We then check when the element gets hidden/shown to known which
         tabs to enable or disable.
       */
      var tabbedView = new TabbedView({views: [
        {
          id: 'valueFilter',
          label: 'Filters',
          view: new recline.View.ValueFilter({
            model: dataset
          })
        },
        {
          id: 'graphControl',
          label: 'Graph options',
          view: views['graph'].view.editor
        },
        {
          id: 'pointDetail',
          label: 'Details',
          view: views['map'].view.sidebar_view
        }
      ]});
      views['graph'].view.editor.el.addClass('well');
      var get_view_selector = function(view_name){
        return function(){
          tabbedView.enableTabs(views[view_name].tabs);
          if (views[view_name].activate_tab){
            tabbedView.selectTab(views[view_name].activate_tab);
          }
        }
      }
      for (var i in views){
        var element = $.extend({}, tabbedView.el);
        element.show = get_view_selector(i);
        element.hide = function(){};
        views[i].view.elSidebar = element;
      }

      // TODO: There is a bug here. MultiView reloads all of the data and discards field renderers
      // I have commented out lines 4076 - 4079 in recline.js to fix this but needs further investigation
      // Is there a way of passing parameters (state?) to MultiView?

      var dataExplorer = new recline.View.MultiView({
        el: this.el,
        model: dataset,
        views: flat_views,
        sidebarViews: [],
        config: {
          readOnly: true
        }
      });
    },
    normalizeFormat: function (format) {
      var out = format.toLowerCase();
      out = out.split('/');
      out = out[out.length-1];
      return out;
    },
    normalizeUrl: function (url) {
      if (url.indexOf('https') === 0) {
        return 'http' + url.slice(5);
      } else {
        return url;
      }
    }
  };
});
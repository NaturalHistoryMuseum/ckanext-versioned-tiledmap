@size: 20;
#{{resource_id}} {
    marker-file: url('symbols/marker.svg');
    marker-allow-overlap: true;
    marker-opacity: 0.2;
    marker-width: @size;
    marker-height: @size;
    marker-clip: false;
    image-filters: colorize-alpha({{heatmap_gradient}});
    opacity: 0.8;
    [zoom >= 7] {
        marker-width: @size * 2;
        marker-height: @size * 2;
    }
}

"""
Plotting utilities for creating static and interactive maps of study areas.
"""

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.patches as mpatches
import contextily as ctx
from adjustText import adjust_text
from titlecase import titlecase
import os
from typing import Optional, Dict, Any, Tuple

# Constants
WEB_MAP_CRS = "EPSG:3857"
GEOGRAPHIC_CRS = "EPSG:4326"

# Default color schemes
DEFAULT_COLORS = {
    'study': 'cornflowerblue',
    'validation': 'indianred',
    'holdout': 'violet'
}

# Default styles for static maps
STATIC_STYLES = {
    'study': {'color': DEFAULT_COLORS['study'], 'edgecolor': 'white', 'alpha': 0.7, 'linewidth': 1},
    'validation': {'color': DEFAULT_COLORS['validation'], 'edgecolor': 'white', 'alpha': 0.7, 'linewidth': 1},
    'holdout': {'hatch': '///', 'color': 'none', 'edgecolor': DEFAULT_COLORS['holdout'], 'linewidth': 1.5}
}

# Default styles for interactive maps
INTERACTIVE_STYLES = {
    'study': {'fillColor': DEFAULT_COLORS['study'], 'color': 'black', 'weight': 1.5, 'fillOpacity': 0.7},
    'validation': {'fillColor': DEFAULT_COLORS['validation'], 'color': 'black', 'weight': 1.5, 'fillOpacity': 0.7},
    'holdout': {'fillColor': DEFAULT_COLORS['holdout'], 'color': 'black', 'weight': 1.5, 'fillOpacity': 0.7}
}


def create_area_map(
        study_gdf,
        validation_gdf,
        holdout_gdf=None,
        title='Analysis Areas',
        save_path=None,
        **kwargs
):
    """
    Creates a publication-quality static map of study, validation, and optional holdout areas.

    Parameters
    ----------
    study_gdf : GeoDataFrame
        Study area geometries
    validation_gdf : GeoDataFrame
        Validation area geometries
    holdout_gdf : GeoDataFrame, optional
        Holdout area geometries
    title : str
        Map title
    save_path : str or Path, optional
        Path to save the map image
    **kwargs : Additional options
        - zoom_level (int): Basemap zoom level (default: 5)
        - figsize (tuple): Figure size (default: (14, 10))
        - basemap_provider: Contextily basemap provider
        - study_style, validation_style, holdout_style (dict): Custom styles
        - legend_loc (str): Legend location (default: 'upper left')
        - show_labels (bool): Show area labels (default: True)
        - label_column (str): Column for labels (default: 'PROVINCE')

    Returns
    -------
    fig, ax : matplotlib Figure and Axes

    Examples
    --------
    # Basic map
    fig, ax = create_area_map(study_gdf, validation_gdf)

    # With holdout and custom title
    fig, ax = create_area_map(
        study_gdf, validation_gdf, holdout_gdf,
        title='Final Analysis Areas',
        save_path='output/map.png'
    )
    """
    # Extract parameters with defaults
    zoom_level = kwargs.get('zoom_level', 5)
    figsize = kwargs.get('figsize', (14, 10))
    basemap = kwargs.get('basemap_provider', ctx.providers.Esri.WorldImagery)
    legend_loc = kwargs.get('legend_loc', 'upper left')
    show_labels = kwargs.get('show_labels', True)
    label_column = kwargs.get('label_column', 'PROVINCE')

    # Get styles (use defaults if not provided)
    study_style = kwargs.get('study_style', STATIC_STYLES['study'])
    validation_style = kwargs.get('validation_style', STATIC_STYLES['validation'])
    holdout_style = kwargs.get('holdout_style', STATIC_STYLES['holdout'])

    # Project to Web Mercator
    study_mercator = study_gdf.to_crs(crs=WEB_MAP_CRS)
    validation_mercator = validation_gdf.to_crs(crs=WEB_MAP_CRS)
    holdout_mercator = holdout_gdf.to_crs(crs=WEB_MAP_CRS) if holdout_gdf is not None else None

    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=figsize, facecolor='black')
    ax.set_facecolor('black')

    # Plot areas
    study_mercator.plot(ax=ax, **study_style)
    validation_mercator.plot(ax=ax, **validation_style)
    if holdout_mercator is not None:
        holdout_mercator.plot(ax=ax, **holdout_style)

    # Add basemap
    ctx.add_basemap(ax, source=basemap, zoom=zoom_level)

    # Add labels if requested
    if show_labels:
        _add_map_labels(ax, study_mercator, validation_mercator, label_column)

    # Add legend
    _add_static_legend(ax, study_style, validation_style, holdout_style,
                       holdout_mercator is not None, legend_loc)

    # Add title
    ax.text(0.98, 0.97, title, transform=ax.transAxes, color='white', fontsize=20,
            fontweight='bold', ha='right', va='top',
            bbox=dict(facecolor='black', alpha=0.5, edgecolor='none', boxstyle='round,pad=0.2'))

    # Clean up
    ax.set_axis_off()
    fig.tight_layout(pad=0)

    # Save if requested
    if save_path:
        _save_figure(save_path, 'static')

    return fig, ax


def create_interactive_map(
        study_gdf,
        validation_gdf,
        holdout_gdf=None,
        save_path=None,
        **kwargs
):
    """
    Creates an interactive Folium map with study, validation, and optional holdout areas.

    Parameters
    ----------
    study_gdf : GeoDataFrame
        Study area geometries
    validation_gdf : GeoDataFrame
        Validation area geometries
    holdout_gdf : GeoDataFrame, optional
        Holdout area geometries
    save_path : str or Path, optional
        Path to save the HTML map
    **kwargs : Additional options
        - zoom_start (int): Initial zoom level (default: 6)
        - show_scale (bool): Show scale control (default: True)
        - show_layer_control (bool): Show layer control (default: True)
        - study_style, validation_style, holdout_style (dict): Custom styles
        - highlight_style (dict): Hover highlight style
        - legend_position (str): 'bottom-right', 'top-left', etc.
        - tooltip_fields (dict): Fields to show in tooltips

    Returns
    -------
    folium.Map : Interactive map object

    Example
    -------
    m = create_interactive_map(
        study_gdf, validation_gdf, holdout_gdf,
        save_path='output/interactive.html'
    )
    """
    import folium
    import geopandas as gpd
    import pandas as pd

    # Extract parameters with defaults
    zoom_start = kwargs.get('zoom_start', 6)
    show_scale = kwargs.get('show_scale', True)
    show_layer_control = kwargs.get('show_layer_control', True)
    legend_position = kwargs.get('legend_position', 'bottom-right')

    # Get styles
    study_style = kwargs.get('study_style', INTERACTIVE_STYLES['study'])
    validation_style = kwargs.get('validation_style', INTERACTIVE_STYLES['validation'])
    holdout_style = kwargs.get('holdout_style', INTERACTIVE_STYLES['holdout'])
    highlight_style = kwargs.get('highlight_style', {'weight': 3, 'color': 'yellow'})

    # Get tooltip configuration
    tooltip_fields = kwargs.get('tooltip_fields', {
        'study': {'fields': ['PROVINCE'], 'aliases': ['Province:']},
        'validation': {'fields': ['PROVINCE'], 'aliases': ['Province:']},
        'holdout': {'fields': ['PROVINCE'], 'aliases': ['Holdout From:']}
    })

    # Reproject to geographic CRS
    study_geo = _safe_reproject(study_gdf, GEOGRAPHIC_CRS)
    validation_geo = _safe_reproject(validation_gdf, GEOGRAPHIC_CRS)
    holdout_geo = _safe_reproject(holdout_gdf, GEOGRAPHIC_CRS) if holdout_gdf is not None else None

    # Calculate center
    center = _calculate_center([study_geo, validation_geo] +
                               ([holdout_geo] if holdout_geo is not None else []))

    # Create map
    m = folium.Map(location=center, zoom_start=zoom_start, tiles=None, control_scale=show_scale)

    # Add tile layers
    _add_tile_layers(m)

    # Add data layers
    _add_geojson_layer(m, study_geo, 'Study Areas', study_style,
                       highlight_style, tooltip_fields['study'])
    _add_geojson_layer(m, validation_geo, 'External Validation', validation_style,
                       highlight_style, tooltip_fields['validation'])
    if holdout_geo is not None:
        _add_geojson_layer(m, holdout_geo, 'Internal Holdout', holdout_style,
                           highlight_style, tooltip_fields['holdout'])

    # Add legend
    _add_interactive_legend(m, study_style, validation_style, holdout_style,
                            holdout_geo is not None, legend_position)

    # Add layer control
    if show_layer_control:
        folium.LayerControl(collapsed=False).add_to(m)

    # Save if requested
    if save_path:
        m.save(str(save_path))
        print(f"✅ Interactive map saved to: {save_path}")

    return m


# ============= Helper Functions =============

def _add_map_labels(ax, study_gdf, validation_gdf, label_column):
    """Add labels to static map with smart positioning."""
    texts = []
    bbox_props = dict(boxstyle="round,pad=0.3", fc="black", ec="none", lw=0, alpha=0.6)

    for gdf, size in [(study_gdf, 10), (validation_gdf, 12)]:
        for idx, row in gdf.iterrows():
            if label_column in row:
                label_point = row.geometry.representative_point()
                texts.append(ax.text(
                    label_point.x, label_point.y, titlecase(str(row[label_column])),
                    color='white', fontsize=size, fontweight='bold',
                    ha='center', bbox=bbox_props
                ))

    if texts:
        adjust_text(texts, ax=ax,
                    arrowprops=dict(arrowstyle='-', color='black', lw=1.5),
                    path_effects=[pe.withStroke(linewidth=3, foreground='white')])


def _add_static_legend(ax, study_style, validation_style, holdout_style, has_holdout, location):
    """Add legend to static map."""
    handles = [
        mpatches.Patch(
            facecolor=study_style.get('color', DEFAULT_COLORS['study']),
            edgecolor=study_style.get('edgecolor', 'white'),
            alpha=study_style.get('alpha', 0.7),
            label='Study Areas' if has_holdout else 'Initial Study Areas'
        ),
        mpatches.Patch(
            facecolor=validation_style.get('color', DEFAULT_COLORS['validation']),
            edgecolor=validation_style.get('edgecolor', 'white'),
            alpha=validation_style.get('alpha', 0.7),
            label='External Validation Area'
        )
    ]

    if has_holdout:
        handles.append(mpatches.Patch(
            facecolor=holdout_style.get('color', 'none'),
            edgecolor=holdout_style.get('edgecolor', DEFAULT_COLORS['holdout']),
            hatch=holdout_style.get('hatch', '///'),
            label='Internal Holdout (Piedmont)'
        ))

    ax.legend(handles=handles, loc=location, fontsize=12,
              facecolor='black', edgecolor='white', labelcolor='white')


def _safe_reproject(gdf, target_crs):
    """Safely reproject and fix invalid geometries."""
    try:
        from shapely.validation import make_valid
        reprojected = gdf.to_crs(target_crs)
        reprojected['geometry'] = reprojected.geometry.apply(make_valid)
        return reprojected
    except ImportError:
        return gdf.to_crs(target_crs)


def _calculate_center(gdfs):
    """Calculate center point from list of GeoDataFrames."""
    import geopandas as gpd
    import pandas as pd

    combined = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))
    bounds = combined.total_bounds
    return [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]


def _add_tile_layers(m):
    """Add default ESRI tile layers to Folium map."""
    import folium

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri — World_Topo_Map',
        name='ESRI Topo'
    ).add_to(m)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri — World_Imagery',
        name='ESRI Imagery'
    ).add_to(m)


def _add_geojson_layer(m, gdf, name, style, highlight, tooltip_config):
    """Add a GeoJSON layer to Folium map with tooltips."""
    import folium

    folium.GeoJson(
        gdf,
        name=name,
        style_function=lambda x: style,
        highlight_function=lambda x: highlight,
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_config['fields'],
            aliases=tooltip_config['aliases'],
            style="font-weight: bold;"
        ),
    ).add_to(m)


def _add_interactive_legend(m, study_style, validation_style, holdout_style, has_holdout, position):
    """Add HTML legend to interactive map."""
    import folium

    position_styles = {
        'bottom-right': 'bottom: 50px; right: 50px;',
        'bottom-left': 'bottom: 50px; left: 50px;',
        'top-right': 'top: 50px; right: 50px;',
        'top-left': 'top: 50px; left: 50px;'
    }

    items = [
        f'<i style="background:{study_style["fillColor"]}; border:1px solid grey; '
        f'width:20px; height:20px; display:inline-block;"></i> Study Areas<br>',
        f'<i style="background:{validation_style["fillColor"]}; border:1px solid grey; '
        f'width:20px; height:20px; display:inline-block;"></i> External Validation<br>'
    ]

    if has_holdout:
        items.append(
            f'<i style="background:{holdout_style["fillColor"]}; border:1px solid grey; '
            f'width:20px; height:20px; display:inline-block;"></i> Internal Holdout<br>'
        )

    legend_html = f"""
    <div style="
        position: fixed;
        {position_styles.get(position, position_styles['bottom-right'])}
        width: 210px;
        border:2px solid grey;
        z-index:9999;
        font-size:14px;
        background-color:rgba(255, 255, 255, 0.85);
        border-radius: 5px;
        padding: 10px;">
        <h4 style="margin-top:0; font-weight: bold;">Legend</h4>
        {''.join(items)}
    </div>
    """

    m.get_root().html.add_child(folium.Element(legend_html))


def _save_figure(save_path, map_type):
    """Save figure with appropriate settings."""
    os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else '.', exist_ok=True)
    if map_type == 'static':
        plt.savefig(save_path, dpi=300, bbox_inches='tight', pad_inches=0, facecolor='black')
    print(f"✅ Map saved to: {save_path}")

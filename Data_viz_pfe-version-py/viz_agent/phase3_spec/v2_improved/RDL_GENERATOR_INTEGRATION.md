"""
INTEGRATION GUIDE: How to use V2 Abstract Specs in RDL Generator

This shows how to modify the RDL generator to use the corrected chart type specifications.
"""

# ============================================================================
# MODIFICATION POINT 1: In rdl_visual_mapper.py
# ============================================================================

# Add this method to map visual type to chart element type:

def _get_chart_type_from_visual(self, visual, dataset) -> str:
    """Get the chart type (Column, Pie, Line, etc.) from visual spec"""
    
    # Check if rendering spec has chart_type (V2 structure)
    if hasattr(visual, 'rendering') and isinstance(visual.rendering, dict):
        chart_type = visual.rendering.get('chart_type')
        if chart_type:
            return chart_type
    
    # Fallback to old method: infer from rdl_type or visual type
    rdl_type = str(getattr(visual, 'rdl_type', 'tablix')).strip().lower()
    vis_type = str(getattr(visual, 'type', 'table')).strip().lower()
    
    # Map RDL type to chart type
    rdl_to_chart = {
        'piecechart': 'Pie',
        'columnchart': 'Column',
        'barchart': 'Bar',
        'linechart': 'Line',
        'scatterchart': 'Scatter',
        'areachart': 'Area',
    }
    
    if rdl_type in rdl_to_chart:
        return rdl_to_chart[rdl_type]
    
    # Map logical type to chart type
    type_to_chart = {
        'pie': 'Pie',
        'bar': 'Column',
        'line': 'Line',
        'scatter': 'Scatter',
    }
    
    return type_to_chart.get(vis_type.lower(), 'Column')


# ============================================================================
# MODIFICATION POINT 2: In rdl_generator.py - Add pie chart support
# ============================================================================

# In the RDLVisualMapper.map_visual() method, add special handling for pie charts:

def map_visual(self, visual, dataset, rect):
    """
    Map visual to RDL element
    
    Special handling for chart types (Column, Pie, Line, etc.)
    """
    
    rdl_type = str(getattr(visual, 'rdl_type', 'tablix')).strip().lower()
    
    # For chart elements, determine chart type and structure accordingly
    if 'chart' in rdl_type or rdl_type in ['piecechart', 'columnchart', 'linechart', 'scatterchart']:
        return self._create_chart_element(visual, dataset, rect)
    elif rdl_type in ['tablix', 'table']:
        return self._create_tablix_element(visual, dataset, rect)
    else:
        return self._create_textbox_element(visual, dataset, rect)


def _create_chart_element(self, visual, dataset, rect):
    """Create a chart element with proper type specification"""
    from lxml import etree
    
    chart_name = self._safe_name(visual.id or 'Chart', 'Chart1')
    
    # Create Chart element
    chart = etree.Element('Chart')
    chart.set('Name', chart_name)
    
    # Position and size
    self._set_position_and_size(chart, rect)
    
    # Data set reference
    ds_ref = etree.SubElement(chart, 'DataSetName')
    ds_ref.text = getattr(dataset, 'rdl_name', dataset.name)
    
    # Determine chart type
    chart_type = self._get_chart_type_from_visual(visual, dataset)  # e.g., "Pie", "Column"
    
    # Build chart based on type
    if chart_type.lower() == 'pie':
        self._build_pie_chart(chart, visual, dataset)
    elif chart_type.lower() in ['column', 'bar']:
        self._build_column_chart(chart, visual, dataset, chart_type)
    elif chart_type.lower() == 'line':
        self._build_line_chart(chart, visual, dataset)
    else:
        self._build_column_chart(chart, visual, dataset, 'Column')  # Default
    
    return chart


def _build_pie_chart(self, chart, visual, dataset):
    """Build a pie chart element"""
    from lxml import etree
    
    # Category axis (groups)
    cat_hier = etree.SubElement(chart, 'ChartCategoryHierarchy')
    cat_members = etree.SubElement(cat_hier, 'ChartMembers')
    cat_member = etree.SubElement(cat_members, 'ChartMember')
    
    # Get X field (category - dimension)
    x_field = self._resolve_x_field_name(visual, dataset)
    
    label = etree.SubElement(cat_member, 'Label')
    label.text = f"=Fields!{x_field}.Value"
    
    group = etree.SubElement(cat_member, 'Group')
    group.set('Name', f'grp_{self._safe_name(x_field, "Category")}')
    
    group_expr = etree.SubElement(group, 'GroupExpressions')
    expr = etree.SubElement(group_expr, 'GroupExpression')
    expr.text = f'=Fields!{x_field}.Value'
    
    # Series (data values)
    series_hier = etree.SubElement(chart, 'ChartSeriesHierarchy')
    series_members = etree.SubElement(series_hier, 'ChartMembers')
    series_member = etree.SubElement(series_members, 'ChartMember')
    
    series_label = etree.SubElement(series_member, 'Label')
    series_label.text = '="Values"'
    
    # Data
    chart_data = etree.SubElement(chart, 'ChartData')
    series_coll = etree.SubElement(chart_data, 'ChartSeriesCollection')
    chart_series = etree.SubElement(series_coll, 'ChartSeries')
    chart_series.set('Name', 'PieValues')
    
    # Get Y field (measure - value)
    y_field = self._resolve_y_field_name(visual, dataset)
    
    chart_data_points = etree.SubElement(chart_series, 'ChartDataPoints')
    chart_data_point = etree.SubElement(chart_data_points, 'ChartDataPoint')
    
    values = etree.SubElement(chart_data_point, 'ChartDataPointValues')
    y_value = etree.SubElement(values, 'Y')
    y_value.text = f'=Sum(Fields!{y_field}.Value)'
    
    series_type = etree.SubElement(chart_series, 'Type')
    series_type.text = 'Pie'  # EXPLICIT PIE TYPE!
    
    # Chart area
    chart_areas = etree.SubElement(chart, 'ChartAreas')
    chart_area = etree.SubElement(chart_areas, 'ChartArea')
    chart_area.set('Name', 'Default')
    
    # Legend
    legends = etree.SubElement(chart, 'ChartLegends')
    legend = etree.SubElement(legends, 'ChartLegend')
    legend.set('Name', 'DefaultLegend')


def _build_column_chart(self, chart, visual, dataset, chart_type='Column'):
    """Build a column/bar chart element"""
    from lxml import etree
    
    # Similar structure to pie but with X and Y axes
    cat_hier = etree.SubElement(chart, 'ChartCategoryHierarchy')
    cat_members = etree.SubElement(cat_hier, 'ChartMembers')
    cat_member = etree.SubElement(cat_members, 'ChartMember')
    
    x_field = self._resolve_x_field_name(visual, dataset)
    label = etree.SubElement(cat_member, 'Label')
    label.text = f"=Fields!{x_field}.Value"
    
    group = etree.SubElement(cat_member, 'Group')
    group.set('Name', f'grp_{self._safe_name(x_field, "Category")}')
    
    group_expr = etree.SubElement(group, 'GroupExpressions')
    expr = etree.SubElement(group_expr, 'GroupExpression')
    expr.text = f'=Fields!{x_field}.Value'
    
    # Series hierarchy
    series_hier = etree.SubElement(chart, 'ChartSeriesHierarchy')
    series_members = etree.SubElement(series_hier, 'ChartMembers')
    series_member = etree.SubElement(series_members, 'ChartMember')
    
    series_label = etree.SubElement(series_member, 'Label')
    series_label.text = '="Values"'
    
    # Data
    chart_data = etree.SubElement(chart, 'ChartData')
    series_coll = etree.SubElement(chart_data, 'ChartSeriesCollection')
    chart_series = etree.SubElement(series_coll, 'ChartSeries')
    
    y_field = self._resolve_y_field_name(visual, dataset)
    chart_series.set('Name', self._safe_name(y_field, 'Series1'))
    
    chart_data_points = etree.SubElement(chart_series, 'ChartDataPoints')
    chart_data_point = etree.SubElement(chart_data_points, 'ChartDataPoint')
    
    values = etree.SubElement(chart_data_point, 'ChartDataPointValues')
    y_value = etree.SubElement(values, 'Y')
    y_value.text = f'=Sum(Fields!{y_field}.Value)'
    
    series_type = etree.SubElement(chart_series, 'Type')
    series_type.text = chart_type  # Column, Bar, etc.
    
    # Chart area with axes
    chart_areas = etree.SubElement(chart, 'ChartAreas')
    chart_area = etree.SubElement(chart_areas, 'ChartArea')
    chart_area.set('Name', 'Default')
    
    # Category axis
    cat_axes = etree.SubElement(chart_area, 'ChartCategoryAxes')
    cat_axis = etree.SubElement(cat_axes, 'ChartAxis')
    cat_axis.set('Name', 'CategoryAxis1')
    
    cat_axis_title = etree.SubElement(cat_axis, 'ChartAxisTitle')
    cat_axis_title_caption = etree.SubElement(cat_axis_title, 'Caption')
    cat_axis_title_caption.text = x_field
    
    # Value axis
    val_axes = etree.SubElement(chart_area, 'ChartValueAxes')
    val_axis = etree.SubElement(val_axes, 'ChartAxis')
    val_axis.set('Name', 'ValueAxis1')
    
    val_axis_title = etree.SubElement(val_axis, 'ChartAxisTitle')
    val_axis_title_caption = etree.SubElement(val_axis_title, 'Caption')
    val_axis_title_caption.text = y_field
    
    # Legend
    legends = etree.SubElement(chart, 'ChartLegends')
    legend = etree.SubElement(legends, 'ChartLegend')
    legend.set('Name', 'DefaultLegend')


# ============================================================================
# RESULT: Pie chart is now generated with Type="Pie"
# ============================================================================
# Before:
# <Chart Name="Feuille_1">
#   <ChartSeriesHierarchy>
#     <ChartMembers>
#       <ChartMember>
#         <Label>="Sales Amount"</Label>
#       </ChartMember>
#     </ChartMembers>
#   </ChartSeriesHierarchy>
#   <!-- NO explicit chart type - defaults to Column! -->
#
# After:
# <Chart Name="PieChart_SalesPerCountry">
#   <ChartType>Pie</ChartType>  <!-- EXPLICIT! -->
#   <ChartSeriesHierarchy>
#     ...categories and values properly mapped for pie...
#   </ChartSeriesHierarchy>
#   <ChartCategoryHierarchy>...</ChartCategoryHierarchy>
#   <!-- Proper pie chart structure -->

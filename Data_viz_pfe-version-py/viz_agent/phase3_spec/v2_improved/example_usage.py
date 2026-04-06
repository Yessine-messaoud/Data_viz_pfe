"""Example: Converting broken spec to fixed spec and then demonstrating RDL generation"""
import json
from viz_agent.phase3_spec.v2_improved.mappers.visualization_mapper import VisualizationMapper
from viz_agent.phase3_spec.v2_improved.validators.spec_autofix import SpecAutoFixer
from viz_agent.phase3_spec.v2_improved.validators.spec_validator import SpecValidator
from viz_agent.phase3_spec.v2_improved.models.visualization_model import VisualSpecV2


def example_1_broken_spec():
    """Example 1: Broken spec with generic 'chart' type"""
    
    broken_spec = {
        "id": "visual_broken_1",
        "source_worksheet": "Feuille 1",
        "title": "Sales per country",
        "visualization": {
            "type": "chart",  # PROBLEM: generic type
            "encoding": {},
            "title": "Sales per country"
        },
        "encoding": {
            "x": None,
            "y": {
                "field": "SalesAmount",
                "aggregation": "SUM",
                "role": "measure"
            }
        },
        "data": {
            "fact_table": "federated.1v3o2r30w2rgsv1aei9is1e9duvo",
            "filters": [],
            "joins": []
        },
        "rendering": {
            "rdl_type": "chart",  # PROBLEM: generic RDL type
            "chart_type": None
        },
        "position": {}
    }
    
    print("=" * 80)
    print("EXAMPLE 1: Fixing broken spec with generic 'chart' type")
    print("=" * 80)
    print("\nBroken spec:")
    print(f"  type: {broken_spec['visualization']['type']}")
    print(f"  rdl_type: {broken_spec['rendering']['rdl_type']}")
    print(f"  encoding.x: {broken_spec['encoding']['x']}")
    print(f"  encoding.y: {broken_spec['encoding']['y']}")
    
    # Auto-fix with Tableau context
    print("\n[Auto-fixing with Tableau context: Pie chart]...")
    fixed_spec, changes = SpecAutoFixer.autofix_visual(
        broken_spec,
        tableau_mark="Pie"
    )
    
    print(f"\nChanges applied: {len(changes)}")
    for change in changes:
        print(f"  ✓ {change}")
    
    print("\nFixed spec:")
    print(f"  type: {fixed_spec['visualization']['type']}")
    print(f"  rdl_type: {fixed_spec['rendering']['rdl_type']}")
    print(f"  encoding.x: {fixed_spec['encoding'].get('x')}")
    print(f"  encoding.y field: {fixed_spec['encoding'].get('y', {}).get('field')}")
    
    # Validate
    print("\n[Validating fixed spec...]")
    validator = SpecValidator()
    dashboard_with_fixed = {
        "pages": [{
            "id": "page1",
            "name": "Page 1",
            "visuals": [fixed_spec]
        }]
    }
    can_proceed, issues = validator.validate_dashboard(dashboard_with_fixed["pages"])
    
    if can_proceed:
        print("✓ Validation PASSED")
    else:
        print(f"✗ Validation FAILED with {len(issues)} issues:")
        for issue in issues:
            print(f"  - {issue}")
    
    return fixed_spec


def example_2_mapping_chain():
    """Example 2: Full mapping chain from Tableau to RDL"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Mapping chain Tableau → Logical → RDL")
    print("=" * 80)
    
    test_cases = [
        ("Pie", "Sales per country"),
        ("Bar", "Revenue by region"),
        ("Line", "Trend over time"),
        ("Treemap", "Hierarchy view"),
    ]
    
    for mark_type, worksheet_name in test_cases:
        mapping = VisualizationMapper.full_chain(mark_type, worksheet_name)
        print(f"\n{mark_type} chart: '{worksheet_name}'")
        print(f"  → logical_type: {mapping['logical_type']}")
        print(f"  → rdl_type: {mapping['rdl_type']}")
        print(f"  → chart_subtype: {mapping['chart_type']}")


def example_3_pie_chart_rdl_generation():
    """Example 3: Generate correct RDL element for pie chart"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Pie chart RDL generation")
    print("=" * 80)
    
    # Get the mapping for pie chart
    mapping = VisualizationMapper.full_chain("Pie", "Sales per country")
    
    print(f"\nPie Chart RDL Configuration:")
    print(f"  RDL Type: {mapping['rdl_type']}")
    print(f"  Chart SubType: {mapping['chart_type']}")
    
    # Show how RDL generator should use this
    rdl_code = f"""
    <Chart Name="PieChart_SalesPerCountry">
        <ChartType>{mapping['chart_type']}</ChartType>
        <ChartAreas>
            <ChartArea Name="Default">
                <!-- Configuration for pie chart -->
            </ChartArea>
        </ChartAreas>
    </Chart>
    """
    
    print(f"\nGenerated RDL snippet:")
    print(rdl_code)


def example_4_batch_dashboard_fix():
    """Example 4: Fix entire dashboard with multiple visuals"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Batch dashboard auto-fix")
    print("=" * 80)
    
    dashboard = {
        "pages": [
            {
                "id": "page1",
                "name": "Executive Dashboard",
                "visuals": [
                    {
                        "id": "visual1",
                        "source_worksheet": "Feuille 1",
                        "title": "Sales per country",
                        "visualization": {"type": "chart", "encoding": {}},  # BROKEN
                        "encoding": {"x": None, "y": {"field": "SalesAmount", "aggregation": "SUM", "role": "measure"}},
                        "data": {"fact_table": "federated.1v3o2r30w2rgsv1aei9is1e9duvo", "filters": [], "joins": []},
                        "rendering": {"rdl_type": "chart"},  # BROKEN
                        "position": {}
                    },
                    {
                        "id": "visual2",
                        "source_worksheet": "Feuille 2",
                        "title": "Revenue trend",
                        "visualization": {"type": "chart", "encoding": {}},  # BROKEN
                        "encoding": {"x": None, "y": {"field": "Revenue", "aggregation": "SUM", "role": "measure"}},
                        "data": {"fact_table": "federated.1v3o2r30w2rgsv1aei9is1e9duvo", "filters": [], "joins": []},
                        "rendering": {"rdl_type": "chart"},  # BROKEN
                        "position": {}
                    }
                ]
            }
        ]
    }
    
    print(f"\nDashboard has {len(dashboard['pages'][0]['visuals'])} broken visuals")
    
    # Auto-fix
    fixed_dashboard, report = SpecAutoFixer.autofix_dashboard(dashboard)
    
    print(f"\nAuto-fix report:")
    print(f"  Total visuals: {report['total_visuals']}")
    print(f"  Fixed visuals: {report['fixed_visuals']}")
    print(f"\nChanges per visual:")
    for visual_id, changes in report['changes_per_visual'].items():
        print(f"  {visual_id}:")
        for change in changes:
            print(f"    ✓ {change}")
    
    return fixed_dashboard


if __name__ == "__main__":
    # Run all examples
    example_1_broken_spec()
    example_2_mapping_chain()
    example_3_pie_chart_rdl_generation()
    example_4_batch_dashboard_fix()
    
    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)

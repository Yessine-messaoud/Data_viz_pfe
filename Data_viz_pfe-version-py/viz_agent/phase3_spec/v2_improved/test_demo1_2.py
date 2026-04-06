"""Test the improved abstract spec system with real demo1.2 data"""
import json
from pathlib import Path
from viz_agent.phase3_spec.v2_improved.validators.spec_autofix import SpecAutoFixer
from viz_agent.phase3_spec.v2_improved.validators.spec_validator import SpecValidator
from viz_agent.phase3_spec.v2_improved.mappers.visualization_mapper import VisualizationMapper


def test_demo1_2_abstract_spec():
    """Test with real demo1.2 abstract spec"""
    
    spec_path = Path("output/demo1_2_demo_abstract_spec.json")
    if not spec_path.exists():
        print(f"❌ {spec_path} not found")
        return
    
    print("=" * 80)
    print(f"Testing with {spec_path.name}")
    print("=" * 80)
    
    # Load spec
    with open(spec_path) as f:
        original_spec = json.load(f)
    
    # Extract dashboard
    dashboard_spec = original_spec.get("dashboard_spec", {})
    pages = dashboard_spec.get("pages", [])
    
    print(f"\n📊 Dashboard: {len(pages)} page(s)")
    for page_idx, page in enumerate(pages):
        visuals = page.get("visuals", [])
        print(f"   Page {page_idx}: {len(visuals)} visual(s)")
        for vis_idx, visual in enumerate(visuals):
            print(f"      Visual {vis_idx}:")
            print(f"         ID: {visual.get('id')}")
            print(f"         Title: {visual.get('title')}")
            print(f"         type: {visual.get('type')}")
            print(f"         rdl_type: {visual.get('rdl_type')}")
    
    # Analyze issues BEFORE fixing
    print("\n" + "=" * 80)
    print("BEFORE FIXES - Issue Detection")
    print("=" * 80)
    
    validator = SpecValidator()
    can_proceed_before, issues_before = validator.validate_dashboard(pages)
    
    if not can_proceed_before:
        print(f"❌ Validation FAILED with {len(issues_before)} issue(s):")
        errors = [i for i in issues_before if i.severity == "error"]
        warnings = [i for i in issues_before if i.severity == "warning"]
        
        if errors:
            print(f"\n  Errors ({len(errors)}):")
            for issue in errors:
                print(f"    [{issue.code}] {issue.message}")
                if issue.fix:
                    print(f"              → Fix: {issue.fix}")
        
        if warnings:
            print(f"\n  Warnings ({len(warnings)}):")
            for issue in warnings:
                print(f"    [{issue.code}] {issue.message}")
    else:
        print("✅ All validations passed")
    
    # Auto-fix
    print("\n" + "=" * 80)
    print("APPLYING AUTO-FIXES")
    print("=" * 80)
    
    # We need to structure the visuals in the format autofix expects
    # For each visual, get the Tableau context from somewhere
    fixed_dashboard, fix_report = SpecAutoFixer.autofix_dashboard(dashboard_spec)
    
    print(f"\n📝 Auto-fix Report:")
    print(f"   Total visuals: {fix_report['total_visuals']}")
    print(f"   Fixed visuals: {fix_report['fixed_visuals']}")
    
    if fix_report['changes_per_visual']:
        print(f"\n   Changes applied:")
        for visual_id, changes in fix_report['changes_per_visual'].items():
            print(f"      {visual_id}:")
            for change in changes:
                print(f"         ✓ {change}")
    
    # Validate AFTER fixing
    print("\n" + "=" * 80)
    print("AFTER FIXES - Validation")
    print("=" * 80)
    
    pages_fixed = fixed_dashboard.get("pages", [])
    can_proceed_after, issues_after = validator.validate_dashboard(pages_fixed)
    
    print(f"\nIssues before fixes: {len(issues_before)}")
    print(f"Issues after fixes: {len(issues_after)}")
    
    if can_proceed_after:
        print("✅ All validations passed!")
    else:
        print(f"⚠️ Still {len(issues_after)} issue(s)")
        for issue in issues_after[:3]:  # Show first 3
            print(f"   [{issue.code}] {issue.message}")
    
    # Show corrected specs
    print("\n" + "=" * 80)
    print("CORRECTED VISUAL SPECIFICATIONS")
    print("=" * 80)
    
    for page_idx, page in enumerate(pages_fixed):
        visuals = page.get("visuals", [])
        for vis_idx, visual in enumerate(visuals):
            print(f"\n📊 Visual: {visual.get('id')}")
            print(f"   Title: {visual.get('title')}")
            print(f"   type: {visual.get('type')} (was: {pages[page_idx]['visuals'][vis_idx].get('type')})")
            print(f"   rdl_type: {visual.get('rdl_type')} (was: {pages[page_idx]['visuals'][vis_idx].get('rdl_type')})")
            
            # Show mapping
            if "visualization" in visual and isinstance(visual["visualization"], dict):
                vis_type = visual["visualization"].get("type")
                rdl_type = visual.get("rendering", {}).get("rdl_type") if isinstance(visual.get("rendering"), dict) else visual.get("rdl_type")
            else:
                vis_type = visual.get("type")
                rdl_type = visual.get("rdl_type")
            
            try:
                mapping = VisualizationMapper.full_chain(
                    # Try to reverse from logical type to Tableau mark
                    next((k for k, v in VisualizationMapper.TABLEAU_TO_LOGICAL.items() if v == vis_type), "Text"),
                    visual.get("title", "")
                )
                print(f"   Mapping verified:")
                print(f"      Tableau → {mapping['logical_type']} → {mapping['rdl_type']} (chart: {mapping['chart_type']})")
            except Exception as e:
                print(f"   Mapping: {vis_type} → {rdl_type}")
    
    # Save corrected spec
    print("\n" + "=" * 80)
    print("SAVING CORRECTED SPEC")
    print("=" * 80)
    
    corrected_spec = original_spec.copy()
    corrected_spec["dashboard_spec"] = fixed_dashboard
    
    output_path = spec_path.with_stem(spec_path.stem + "_CORRECTED_V2")
    with open(output_path, "w") as f:
        json.dump(corrected_spec, f, indent=2)
    
    print(f"✅ Corrected spec saved to: {output_path}")
    
    return corrected_spec


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    test_demo1_2_abstract_spec()

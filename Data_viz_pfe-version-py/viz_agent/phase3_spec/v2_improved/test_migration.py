"""Test the migration adapter with real demo1.2 data"""
import json
from pathlib import Path
from viz_agent.phase3_spec.v2_improved.migration_adapter import SpecMigrationAdapter, patch_fact_table_in_migrated_spec
from viz_agent.phase3_spec.v2_improved.validators.spec_autofix import SpecAutoFixer
from viz_agent.phase3_spec.v2_improved.validators.spec_validator import SpecValidator


def test_migration_demo1_2():
    """Test migration with real demo1.2 abstract spec"""
    
    spec_path = Path("output/demo1_2_demo_abstract_spec.json")
    if not spec_path.exists():
        print(f"❌ {spec_path} not found")
        return
    
    print("=" * 80)
    print("MIGRATION TEST: Old Spec -> New V2 Structure")
    print("=" * 80)
    
    # Load old spec
    with open(spec_path) as f:
        old_spec = json.load(f)
    
    print(f"\n📥 Loaded: {spec_path.name}")
    print(f"   Version: {old_spec.get('version')}")
    
    # Show old structure
    old_visual = old_spec["dashboard_spec"]["pages"][0]["visuals"][0]
    print(f"\n📋 Old Visual Structure:")
    print(f"   type: {old_visual.get('type')}")
    print(f"   rdl_type: {old_visual.get('rdl_type')}")
    print(f"   Keys: {list(old_visual.keys())}")
    
    #  Migrate
    print(f"\n[*] Migrating to V2 structure...")
    migrated_spec = SpecMigrationAdapter.migrate_spec_old_to_v2(old_spec)
    
    # Patch fact table from semantic model
    semantic_model = old_spec.get("semantic_model", {})
    fact_table = semantic_model.get("fact_table", "federated.1v3o2r30w2rgsv1aei9is1e9duvo")
    migrated_spec = patch_fact_table_in_migrated_spec(migrated_spec, fact_table)
    
    # Show new structure
    new_visual = migrated_spec["dashboard_spec"]["pages"][0]["visuals"][0]
    print(f"\n📋 New Visual Structure (V2):")
    print(f"   visualization.type: {new_visual['visualization'].get('type')}")
    print(f"   rendering.rdl_type: {new_visual['rendering'].get('rdl_type')}")
    print(f"   rendering.chart_type: {new_visual['rendering'].get('chart_type')}")
    print(f"   Keys: {list(new_visual.keys())}")
    print(f"   encoding.y: {new_visual['encoding'].get('y')}")
    
    # Validate migrated spec
    print(f"\n" + "=" * 80)
    print("VALIDATION OF MIGRATED SPEC")
    print("=" * 80)
    
    pages = migrated_spec.get("dashboard_spec", {}).get("pages", [])
    validator = SpecValidator()
    can_proceed, issues = validator.validate_dashboard(pages)
    
    print(f"\nValidation result: {'✅ PASSED' if can_proceed else '❌ FAILED'}")
    if issues:
        print(f"Issues: {len(issues)}")
        for issue in issues[:3]:
            print(f"  [{issue.code}] {issue.severity}: {issue.message}")
    
    # Apply auto-fixes
    print(f"\n" + "=" * 80)
    print("APPLYING AUTO-FIXES TO MIGRATED SPEC")
    print("=" * 80)
    
    fixed_dashboard, fix_report = SpecAutoFixer.autofix_dashboard(migrated_spec["dashboard_spec"])
    migrated_spec["dashboard_spec"] = fixed_dashboard
    
    print(f"\nFixed visuals: {fix_report['fixed_visuals']}/{fix_report['total_visuals']}")
    for visual_id, changes in fix_report['changes_per_visual'].items():
        print(f"  {visual_id}:")
        for change in changes:
            print(f"    ✓ {change}")
    
    # Final validation
    print(f"\n" + "=" * 80)
    print("FINAL VALIDATION")
    print("=" * 80)
    
    pages_final = migrated_spec.get("dashboard_spec", {}).get("pages", [])
    can_proceed_final, issues_final = validator.validate_dashboard(pages_final)
    
    print(f"\nFinal result: {'✅ PASSED' if can_proceed_final else '⚠️ NEEDS REVIEW'}")
    if issues_final:
        print(f"Remaining issues: {len(issues_final)}")
        for issue in issues_final[:3]:
            print(f"  [{issue.code}] {issue.severity}: {issue.message}")
    
    # Show final corrected visual
    final_visual = migrated_spec["dashboard_spec"]["pages"][0]["visuals"][0]
    print(f"\n" + "=" * 80)
    print("FINAL CORRECTED VISUAL")  
    print("=" * 80)
    print(f"\n{json.dumps(final_visual, indent=2)}")
    
    # Save migrated and fixed spec
    output_path = spec_path.with_stem(spec_path.stem + "_V2_MIGRATED_FIXED")
    with open(output_path, "w") as f:
        json.dump(migrated_spec, f, indent=2)
    
    print(f"\n✅ Saved to: {output_path}")
    
    return migrated_spec


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    test_migration_demo1_2()

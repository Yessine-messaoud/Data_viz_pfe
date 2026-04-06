from __future__ import annotations

import argparse
import json
from pathlib import Path

from viz_agent.models.abstract_spec import AbstractSpec
from viz_agent.phase3_spec.spec_correction import SpecCorrectionEngine


def correct_spec(spec: AbstractSpec) -> AbstractSpec:
    engine = SpecCorrectionEngine()
    warnings = list(spec.warnings or [])

    for page in spec.dashboard_spec.pages:
        for visual in page.visuals:
            result = engine.correct(visual, spec.semantic_model)
            visual.type = result.visual_spec.type
            visual.rdl_type = result.visual_spec.rdl_type
            visual.data_binding = result.visual_spec.data_binding

            for message in result.corrections:
                warnings.append(f"{visual.id}: {message}")
            for issue in result.issues:
                warnings.append(f"{visual.id}: {issue}")

    spec.warnings = warnings
    return spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate, clean, and correct AbstractSpec JSON for RDL readiness")
    parser.add_argument(
        "--input",
        default="output/DEMO_Complete/demo_ssms_demo_abstract_spec.json",
        help="Input AbstractSpec JSON path",
    )
    parser.add_argument(
        "--output",
        default="output/DEMO_Complete/demo_ssms_demo_abstract_spec.corrected.json",
        help="Output corrected AbstractSpec JSON path",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    spec = AbstractSpec.model_validate(raw)
    corrected = correct_spec(spec)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(corrected.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Corrected AbstractSpec written to: {output_path}")
    print(f"Total warnings: {len(corrected.warnings)}")


if __name__ == "__main__":
    main()

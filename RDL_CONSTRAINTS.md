# RDL Constraints For Future Executions

This project enforces mandatory constraints before writing `output/powerbi-paginated-report.rdl`.

## Mandatory criteria

- `RDL-001`: Root `Report` exists with 2016 report definition namespace.
- `RDL-002`: At least one `ReportSection` exists.
- `RDL-003`: Each `ReportSection` includes mandatory `Width`.
- `RDL-004`: `Body/Height` exists.
- `RDL-005`: `Page` exists.
- `RDL-006`: `EmbeddedData` is forbidden under `Report` for 2016 schema.
- `RDL-007`: `ConnectString` is forbidden in local generated RDL to avoid credential mode mismatch and processing errors.
- `RDL-008`: `Body` must contain visible `ReportItems` (textbox with value) to avoid blank report rendering.

## Ordering guideline (schema-safe)

Use this root element sequence:

- `AutoRefresh`
- `Description`
- `CustomProperties`
- `ReportSections`

## Execution constraints

- If any mandatory criterion fails, generation stops with an explicit error.
- Quality gate runs before RDL generation:
- AutoFixer (DAX normalization)
- ModelValidator (lineage/model consistency)
- DAXValidator (function checks)
- Structural RDL constraints run after XML build and before file write.
- Any generated `EmbeddedData` node must fail generation.
- Any generated `ConnectString` node must fail generation.
- Any generated RDL without visible body content must fail generation.

## Operational rule

Always execute `npm run test` and `npm run demo:full` after changes affecting adapter, export, or report generation.

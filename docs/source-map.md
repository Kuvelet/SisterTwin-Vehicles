# Source map and external data contracts

Start with the README for the business workflow, then follow these files in execution order. This is the real application source with documented sanitization. It is not a parallel educational implementation.

| File | What to inspect |
| --- | --- |
| [CsvInput.cs](../src/AppSource/CsvInput.cs) | Encoding detection, strict parsing, limits, canonical Windows-1252 output, SHA-256 |
| [InputPanel.cs](../src/AppSource/InputPanel.cs) | Vehicle-list preview, template and format guidance |
| [Program.cs](../src/AppSource/Program.cs) | Desktop layout, worker heartbeat, complete request publication, status transitions |
| [LiveLogPanel.cs](../src/AppSource/LiveLogPanel.cs) | Incremental log reading and shared-file access |
| [sistertwin_worker.py](../src/Worker/sistertwin_worker.py) | Request schema, queue claiming, serial processing, subprocess and completion checks |
| [layout_support.py](../src/Workflow/layout_support.py) | Configuration and atomic status-file helpers |
| [run_sistertwin_workflow.py](../src/Workflow/run_sistertwin_workflow.py) | Seven-stage coordinator, session lock, decision allowlist, paired publication |
| [sistertwin_upload.py](../src/Workflow/sistertwin_upload.py) | Checksums, input backup and restoration boundaries |
| [refresh_sistertwin_input.py](../src/Workflow/refresh_sistertwin_input.py) | Backend CSV validation, raw replacement, expanded-count verification |
| [v0 procedure](../sql/dbo.usp_CreateSisterTwin_Vehicles_Raw_Expanded_v0.sql) | Inclusive year expansion |
| [transfer_sistertwin_to_vcdb.py](../src/Workflow/transfer_sistertwin_to_vcdb.py) | Staging-table recreation, batched transfer and multiplicity checks |
| [validate_sistertwin_vehicles.py](../src/Workflow/validate_sistertwin_vehicles.py) | VCdb identity joins and return of all validation results |
| [v7 procedure](../sql/dbo.usp_CreateSisterTwin_DescriptionGapReport_v7.sql) | Bidirectional anti-joins, application details, target dictionary match, part-set comparison and ranking |
| [export_vcdb_validation.py](../src/Workflow/export_vcdb_validation.py) | Validation workbook, literal text and dimension verification |
| [export_sistertwin_v7.py](../src/Workflow/export_sistertwin_v7.py) | 46-column streamed gap workbook, Excel limits and archive integrity |

## External inputs, not bundled databases

The configured catalog database must expose `dbo.PIM_BaseApplications`, including the fields selected by the v7 `AppDescriptions` CTE. Its `Part Number` becomes `Part` in the report. The product-management database must expose `dbo.v_PIM_Vehicle_Dictionary`; the analysis reads Make, Model, Year, Engine, and Region. The SQL export maps a company-specific catalog schema to `dbo` without changing the selected business columns.

[external-data-contracts.json](external-data-contracts.json) records the inspected column names, types, byte lengths, precision, scale, and nullability for these two inputs. It contains no rows, internal database names, or underlying company view definitions. It is a reconstruction reference, not a promise that a replacement schema alone reproduces the source data's meaning. For `nvarchar`, the byte length is twice the maximum character count; `-1` denotes a MAX type.

VCdb validation requires:

- `dbo.BaseVehicle`: MakeID, ModelID, YearID
- `dbo.Make`: MakeID, MakeName
- `dbo.Model`: ModelID, ModelName

The identity check joins IDs inside VCdb and matches the resulting make/model names and year against the expanded relationship list. Access to an appropriately licensed vehicle database remains an external requirement.

## Objects owned by this workflow

The [raw input DDL](../sql/001_raw_input.sql) reconstructs the inspected input table's columns. It is a metadata-derived installation aid, not an original application script. The v0 procedure rebuilds expanded rows. Python recreates the VCdb staging input and catalog validation-result table. The v7 procedure rebuilds its output table.

Generated analysis tables are intermediate/output state; they are not the authoritative company catalog. Their rebuilds make isolated database testing and the shared workflow lock essential during deployment.

## Application-line versus grouping grain

Part-set completeness uses distinct Part values per reference and target make/model/year/description. It does not count application lines. The winner retains all eligible rows, including differing conditions and positions. GapGroupID additionally identifies a source/target/year/description/part grouping; MissingRegionGroupID adds the target region. Neither dense-rank identifier is a permanent catalog-record key.

## Import-file boundary

No source file here generates the final catalog import file. The application generates the two Excel reports. The documented downstream manual preparation selects approved Include candidates, substitutes target vehicle fields, removes analysis-only columns, reviews nonportable qualifiers and text formatting, and validates the receiving file in PIM before import. Company-specific exception lists and unresolved historical text replacements are not encoded as generic automation rules.

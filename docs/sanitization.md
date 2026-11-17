# Sanitization record

Prepared November 17, 2026 from the local application backend and read-only exports of the installed SQL procedures.

## Preserved implementation

The desktop request flow, CSV validation, Python queue/worker/coordinator, SQL selection algorithm, report fields, error handling, and export logic are retained. This is not a rewritten sample. Changes below are deliberate; no production application files were edited.

| Change | Public form |
| --- | --- |
| Internal shared path | `\\FILESERVER\SisterTwin` |
| Worker hostname and display messages | `WORKERHOST` |
| SQL endpoints | `CATALOGSQL\CATALOG` and `VEHICLESQL` |
| Database names | `CatalogDb`, `VehicleDb`, `ProductManagementDb` |
| Company-specific catalog source schema | `dbo` |
| Operational settings | `settings.example.json`; actual settings ignored |
| Certificate-validation configuration | Public example uses verification; private original retained separately |
| Company icon/logo | Assets omitted and project-resource references removed; optional logo-loading code retained |
| Raw input DDL | New installation aid reconstructed from inspected column metadata |
| Tests | Applicable original tests adapted to temporary paths/current backup filename; added current publisher/decision-contract checks |

The private sanitization map records exact source-file hashes and identifier substitutions. It is excluded from this repository because it contains the original operational identifiers.

## Excluded material

Credentials, actual settings, downloadable company datasets/workbooks, raw logs, queue/run history, compiled executables, dependency build outputs, standalone company artwork, older deployment packages, private project memory, and definitions of external company catalog/dictionary views are excluded from the source package.

The owner separately authorized publishing the visible contents of a real deployed-app recording, confirming the on-screen data is not confidential. That recording shows the existing vehicle list, live progress and report excerpts, including the deployed interface's branding and operational labels. This media exception does not publish the underlying workbooks, private backup or operational configuration files.

The public data-contract metadata describes input columns without providing rows or pretending to recreate the external databases. The small fictional worked example explains the selection rule; it is not a second implementation. The old offline UI screenshot has been replaced by the authorized real-run recording.

The previous educational sample and its generated workbook/test evidence have been removed from the current repository contents. Earlier commits retain history; this change is not a history purge.

## Publication scope

Sanitization does not establish permission to publish company-owned source. The owner confirmed authorization to publish this implementation subject to sanitization. The package was checked against the exclusions above before publication. The private archive must remain in an approved private location even after the sanitized implementation is published.

# Verification and limitations

Verified November 17, 2026.

## Sources and version authority

The current local backend, shared deployment, historical project files/tests, saved project memory, and referenced project chat were inspected. Current v0/v7 procedure definitions were exported with read-only metadata queries. No production analysis procedure, importer, or worker deployment was executed for this work.

The installed v7 uses part-list completeness before engine preference. An older saved SQL file used the earlier ranking design. Public SQL comes from the installed definitions, not that older file. Local source includes matched run-start timestamps for both report filenames. Source equivalence with the deployed executable has not been independently established; both were preserved privately.

The owner confirmed that the initial phase resulted in 60,000 successful catalog application-line imports after cleanup and validation, and that they built the tool from scratch after listening to team needs. An import ledger and exact historical code version were not independently reconciled. Current report counts must not be substituted for that result.

## Sanitized source checks

- The actual sanitized .NET 8 Windows Forms application passed Release single-file Windows x64 publication.
- Thirty offline tests passed against an isolated copy of the actual Python workflow modules. These cover CSV encoding/ranges/headers, upload checksums and restoration, transaction commit/rollback behavior, transfer multiplicities, VCdb result checks, workflow locks, decision labels, literal Excel text and report dimensions, export-count mismatches, and paired report publication.
- Tests block real SQL connections. Mocked SQL responses test orchestration behavior, not execution of the stored procedure bodies.
- The report publisher was checked for matching timestamps, invalid timestamps, and a missing staged workbook. Workbook contents are tested separately through the real exporters.
- Operational identifiers and credential-pattern scans were performed over the publication allowlist. Only source, documentation, test code, a generic configuration example, structural data contracts, and the offline UI image are packaged. Build outputs and actual settings are excluded.
- Documentation links were checked against packaged files. The educational selection sample, fictional downloadable workbook, and its old test-results file are no longer part of the current package.

## Limits and reconstruction risks

No live end-to-end SQL run, catalog import, performance benchmark, or independent physical-fit validation was performed. The tests do not establish SQL collation equivalence, completeness of external vehicle relationships, or correctness of every source application. The raw-table DDL is reconstructed column metadata, not a full database migration including all permissions/indexes.

The source retains its original coupling to named databases, a shared Windows folder, and one worker host. Those locations are now placeholders and must be configured consistently across Python, SQL, C#, and launch scripts. The settings example changes the certificate-verification default; see the sanitization record.

The private backup contains 262 files, including the original backend, shared files/run history, historical project sources/tests, installed SQL metadata/definitions, dependency inventory, recovery notes, and hash manifests. Its ZIP entries were verified against SHA-256 hashes; no copied source file changed during its individual copy. It is a live snapshot, not a transactionally consistent SQL backup or an off-device disaster-recovery copy.

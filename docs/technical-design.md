# Technical design

## Data model and transformations

The input schema is `Years, Make_A, Model_A, Make_B, Model_B`. Each inclusive range becomes individual pair-years. The expected expansion is the sum of `EndYear - StartYear + 1`; the coordinator verifies the expanded count before validation. The input supports UTF-8 and Windows-1252, retaining accented vehicle names. Checks cover required fields, lengths, file size, pair count, and year ranges.

VCdb validation joins BaseVehicle to Make and Model using their IDs, then matches each input side by make/model names and year. Both sides must exist for a pair-year to enter analysis. Invalid years remain visible in the validation report. This validates identity, not the proposed relationship or fitment. The custom VCdb staging table is recreated because database refreshes can remove custom objects. Transfers compare row multiplicities, rather than trusting row totals alone.

The installed SQL procedure normalizes pair names and converts years, retaining valid pair-years. It selects distinct source application details and finds missing descriptions with left anti-joins in both directions. The gap is at the description level: it is not a comprehensive detector of missing individual part applications within an already-covered description. Directional results are combined with `UNION ALL`.

The target dictionary is joined using missing make, missing model, year, and reference **engine text**. NULL engine text is compared as an empty string. This is not an engine-ID interchangeability test. The joined target region must be non-NULL for a row to participate in selection. Multiple target regions or differing application details can expand the report. A region string can itself represent multiple markets; a row is not necessarily one country.

## Reference selection

The selection group is missing make/model/year/description. Region is not an additional partition in the selection rule. For each group:

1. Remove NULL-target-region rows from selection calculations, but retain them as excluded report rows.
2. Fail closed if any eligible row has a NULL, empty, or whitespace-only part number.
3. Count distinct parts across the group and per reference make/model.
4. Keep references whose distinct count equals the union count. This proves completeness because each reference set is a subset of that union; equal counts between unrelated sets would not prove equality.
5. Rank complete references by engine category, eligible row count descending, then make/model.
6. Include every eligible row from the winning reference. Exclude other references. Send groups without a complete reference for review.

Engine preference is all blank, all specified, then mixed. It is a deterministic business rule, not evidence that blank engines are inherently safer. Completeness takes precedence. Preserving all winning rows retains positions, conditions, notes, and other source details; this does not eliminate inherited overlaps.

The five decision labels are:

- `Include - selected reference vehicle`
- `Exclude - another reference vehicle selected`
- `Exclude - Missing Region is NULL`
- `Needs review - no reference contains all eligible parts`
- `Needs review - missing part number`

The coordinator checks this exact allowlist before committing that stage. Group IDs use dense ranks over source/target/year/description/part, with a separate ID adding missing region. Expansion reasons explain application-detail and region multiplication. These are report grouping keys, not durable catalog identities.

## Architecture and reliability

The Windows Forms client writes a complete temporary request directory, then renames it into the shared queue. The single Python worker claims it by moving it into run history. Upload requests include a checksum; current-list requests snapshot the shared input at execution time. An uploaded list becomes the shared default, with a backup of the previous list.

The worker invokes a fixed workflow subprocess and captures its log. Heartbeats and status JSON drive the client. The progress bar signals activity, not percent completion. Closing the client does not cancel server-side work.

A SQL session application lock spans the workflow; transactions protect individual stages. There is no distributed transaction covering both databases and files. A late failure can leave earlier stages committed. Interrupted requests are not blindly replayed, and independent jobs that ignore the lock can still interfere.

The exporter fetches batches of 2,000 rows into an openpyxl write-only workbook. It checks column order, decision totals, Excel row/text limits, and ZIP integrity. Strings are explicitly written as text to retain leading zeros and prevent formula-like part identifiers from becoming formulas. Both workbooks are staged and published together by directory rename. The worker additionally checks exit status and report files before declaring success.

## Deployment and tradeoffs

Users launch a framework-dependent .NET 8 Windows x64 executable from a shared location. They need the Windows Desktop Runtime and share access, not Python or SQL tools. A dedicated Windows host runs the Python worker after sign-in using Windows authentication for SQL. Backend source/configuration stays on the worker host; requests, reports, and history are shared.

This reuses the team's Windows and SQL environment and avoids requiring a web service. Tradeoffs include dependence on a signed-in, awake host, shared-folder permissions, serial throughput, and growing history without automated retention. A hidden folder is not an access-control boundary. Request JSON does not establish authenticated user identity.

## Evolution

Earlier iterations expanded years, added bidirectional description-gap analysis, and exposed detailed application and region expansion. Historical approaches mixed references, introducing ambiguity. An earlier v7 ranked engines first. The installed current v7 instead requires complete eligible part coverage before tie-breaking. A saved SQL export still contained the older design when this case study was investigated; the installed definition was inspected read-only to resolve the discrepancy.

Current local source also includes a shared run-start timestamp for both workbook filenames. The version label alone did not identify that patch. SSIS was explored earlier, but the current coordinator invokes SQL through Python. No automatic PIM import is implemented.

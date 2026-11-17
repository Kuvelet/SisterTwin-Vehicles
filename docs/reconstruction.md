# Build, configuration, and recovery

This guide is for reconstructing the actual application in an authorized environment. It is not a one-command demo. The source is inspectable and the client can be built without company databases; full workflow execution requires configured external sources and Windows permissions.

## What is preserved

The repository keeps the desktop client, worker and launch scripts, Python workflow/export modules, current installed v0/v7 SQL definitions, a raw-table installation aid, and data-contract documentation. The exact operational configuration, deployed executable, historical sources, input files, reports and run history belong in the separate private archive.

The installed SQL definitions are the authority for this captured version. A historical saved SQL file contained the prior engine-first design. Do not substitute it for the part-list-first v7 retained here. Source-to-deployed-binary equivalence has not been independently established, so the private archive preserves the deployed executable separately.

## Requirements

- Windows x64 with a .NET SDK capable of targeting `net8.0-windows`; clients require the .NET 8 Windows Desktop Runtime.
- Python with the packages in [requirements.txt](../src/Workflow/requirements.txt). The captured environment used Python 3.14. Dependency ranges are the actual source requirements, not a reproducible lockfile; the private archive retains the installed package inventory.
- Microsoft ODBC Driver 18 for SQL Server, the required catalog/vehicle data sources, and Windows-account SQL access.
- A shared folder accessible to clients and the worker, with appropriate share and NTFS permissions.

## Configure an isolated environment first

1. Copy [settings.example.json](../src/Config/settings.example.json) to `src/Config/settings.json`. Set the actual shared root, worker computer, Python executable, and display preference. Keep the real file private and ignored by Git.
2. Replace the placeholder SQL server/database identifiers in the Python connection code and v7 SQL references. These remain in their original source locations to avoid silently refactoring the implementation. Search for `CATALOGSQL`, `VEHICLESQL`, `CatalogDb`, `VehicleDb`, and `ProductManagementDb`.
3. Update the desktop `Root` and worker-host checks/messages in Program.cs. Search for `FILESERVER` and `WORKERHOST`. Updating Python settings does not update these compiled client constants.
4. Review the Python paths in the worker `.cmd` launchers. A configured interpreter in JSON does not replace the interpreter used to start the worker itself.
5. Provision `Control/Data`, `Control/Queue`, `Control/Runs`, and `Reports` under the configured shared root. Supply an authorized vehicle-pair CSV with the five documented columns. Keep Queue empty when reconstructing; never replay archived requests.
6. Provision compatible catalog/PIM/VCdb inputs using the [data contracts](source-map.md). In the target catalog database, review and install `001_raw_input.sql`, followed by v0 and v7. The exported procedures use CREATE, so an existing installation needs a reviewed ALTER/deployment operation; blindly rerunning CREATE will fail. Python recreates its staging/result tables during execution.
7. Configure database and share access for the actual worker account. The public configuration defaults to certificate verification; the SQL endpoints need trusted certificates. The original private setting is preserved only in the private archive.

This application is coupled to its documented data contracts. Changing names is not sufficient if the replacement databases use different semantics, text encodings, collation, or fitment qualifiers.

## Build the desktop application

From the repository root:

```powershell
dotnet publish src/AppSource/SisterTwin.Launcher.csproj -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -p:EnableSingleFileAnalyzer=false -p:DebugType=None -p:DebugSymbols=false --configfile src/AppSource/NuGet.Config
```

The executable is in `src/AppSource/bin/Release/net8.0-windows/win-x64/publish/`. Deploy the file from **publish**, not the parent build directory. The checked-in Build_App.ps1 performs the same build; building does not deploy or restart the worker. Company icon/logo resources were omitted, so the sanitized build has no company branding.

## Offline verification

```powershell
python -m pip install -r src/Workflow/requirements.txt
python -m unittest discover -s tests -v
```

Tests copy the actual workflow modules into a temporary backend and supply temporary configuration. Live SQL connections are blocked. Tiny unit-test rows and mock connections exercise validation, transactions, export and failure handling; they are not a sample catalog or replacement database.

Passing these checks does not prove SQL integration or part fitment. The source-only build and offline tests can be run without creating `src/Config/settings.json`.

## Validate and deploy

Use the configured Check_Setup.cmd for preflight. It does not run the analysis stored procedures, but it does contact the configured databases and test file creation. It is not an offline test.

Perform an end-to-end run in a separate test environment. Reconcile input expansion, vehicle-validation counts, decision totals, report contents, and paired publication. Confirm that the desktop reconnects to active requests and that failures remain visible. Then deploy through the organization's approved process, ensuring the old worker is idle and stopped before replacing it. Do not start another worker or independent analysis job against the same live tables.

The captured operational model starts the worker after Windows sign-in. It depends on the host being signed in, awake, and connected. It is not a Windows service. Configure startup only after isolated validation. Closing the client or progress viewer does not stop SQL work.

## Recovery boundaries

Restore source/configuration, current SQL definitions, and approved input independently from run history. Retain historical reports and logs for investigation, but do not use old Queue or status files as new work. Per-stage SQL commits mean a failed run may have changed earlier tables; inspect logs before retrying.

The private archive is a file-and-definition snapshot, not a backup of the underlying company databases. A complete disaster-recovery plan also requires approved database backups, permissions, certificates, licensed VCdb access, and an off-device copy under the organization's retention policy. None of those should be inferred from a public Git repository.

$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot 'AppSource\SisterTwin.Launcher.csproj'
$output = Join-Path $PSScriptRoot 'AppSource\bin\Release\net8.0-windows\win-x64\publish'
# No trimming. Disable the optional NuGet-based analyzer for an offline build.
dotnet publish $project -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -p:EnableSingleFileAnalyzer=false -p:DebugType=None -p:DebugSymbols=false --configfile (Join-Path $PSScriptRoot 'AppSource\NuGet.Config')
if ($LASTEXITCODE -ne 0) { throw 'Build failed. Shared executable was not changed.' }
Write-Host "Built executable: $output\SisterTwin.Launcher.exe"
Write-Host 'Nothing was deployed. Close client apps before replacing a shared executable.'

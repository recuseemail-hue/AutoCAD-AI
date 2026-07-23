$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectFile = Join-Path $projectRoot "AutoCadAIPlugin.csproj"
$releaseOutput = Join-Path $projectRoot "bin\Release\net10.0"
$distributionDirectory = Join-Path $projectRoot "dist"

dotnet restore $projectFile
if ($LASTEXITCODE -ne 0) {
    throw "dotnet restore failed with exit code $LASTEXITCODE."
}

dotnet build $projectFile --configuration Release --no-restore
if ($LASTEXITCODE -ne 0) {
    throw "dotnet build failed with exit code $LASTEXITCODE."
}

New-Item -ItemType Directory -Path $distributionDirectory -Force | Out-Null
$sourceDll = Join-Path $releaseOutput "AutoCadAIPlugin.dll"
$sourcePdb = Join-Path $releaseOutput "AutoCadAIPlugin.pdb"
$destinationDll = Join-Path $distributionDirectory "AutoCadAIPlugin.dll"
$destinationPdb = Join-Path $distributionDirectory "AutoCadAIPlugin.pdb"

try {
    Copy-Item -LiteralPath $sourceDll -Destination $destinationDll -Force
    Copy-Item -LiteralPath $sourcePdb -Destination $destinationPdb -Force
}
catch [System.IO.IOException] {
    [xml]$project = Get-Content -LiteralPath $projectFile
    $version = [string]$project.Project.PropertyGroup.Version
    $destinationDll = Join-Path $distributionDirectory "AutoCadAIPlugin-v$version.dll"
    $destinationPdb = Join-Path $distributionDirectory "AutoCadAIPlugin-v$version.pdb"
    Copy-Item -LiteralPath $sourceDll -Destination $destinationDll -Force
    Copy-Item -LiteralPath $sourcePdb -Destination $destinationPdb -Force
    Write-Warning "The canonical DLL is loaded by AutoCAD. Wrote a versioned build instead."
}

Write-Host "Plugin ready: $destinationDll"

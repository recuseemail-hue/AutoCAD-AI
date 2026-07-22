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
Copy-Item -LiteralPath (Join-Path $releaseOutput "AutoCadAIPlugin.dll") `
    -Destination $distributionDirectory -Force
Copy-Item -LiteralPath (Join-Path $releaseOutput "AutoCadAIPlugin.pdb") `
    -Destination $distributionDirectory -Force

Write-Host "Plugin ready: $(Join-Path $distributionDirectory 'AutoCadAIPlugin.dll')"

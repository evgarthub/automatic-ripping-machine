param(
    [string]$ImageName = "automatic-ripping-machine",
    [string]$ImageTag = "",
    [string]$DestDir = "\\TRUENAS\nextcloud\webserver\automatic-ripping-machine"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrEmpty($ImageTag)) {
    $ImageTag = Get-Date -Format "yyyyMMdd-HHmm"
}

$FullImage = "${ImageName}:${ImageTag}"
$TarFile = Join-Path $PSScriptRoot "${ImageName}_${ImageTag}.tar"

Write-Host "==> Building image $FullImage"
docker build -t $FullImage $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw "docker build failed" }

Write-Host "==> Saving image to $TarFile"
docker save -o $TarFile $FullImage
if ($LASTEXITCODE -ne 0) { throw "docker save failed" }

if (-not (Test-Path -LiteralPath $DestDir)) {
    throw "Destination not reachable: $DestDir"
}

Write-Host "==> Copying to $DestDir"
Copy-Item -LiteralPath $TarFile -Destination $DestDir -Force

Write-Host "==> Done: $(Join-Path $DestDir (Split-Path $TarFile -Leaf))"

$remove = Read-Host "Remove local tar file? (y/N)"
if ($remove -eq 'y') {
    Remove-Item -LiteralPath $TarFile
    Write-Host "Removed $TarFile"
}

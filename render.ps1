# Render Quarto site, working around a bug in the bundled quarto.cmd that
# breaks when the install path contains spaces (Program Files).
#
# Usage:
#   .\render.ps1                       # render full site
#   .\render.ps1 services.qmd          # render a single file
#   .\render.ps1 countries/Botswana.qmd
#
# The wrapper references %QUARTO_DENO% unquoted; cmd then word-splits the
# "C:\Program Files\..." path. We pre-set QUARTO_DENO to its 8.3 short path
# and invoke quarto.cmd through its short path too.

$ErrorActionPreference = 'Stop'

$quartoCandidates = @(
  "C:\Program Files\Positron\resources\app\quarto\bin\quarto.cmd",
  "C:\Program Files\RStudio\resources\app\bin\quarto\bin\quarto.cmd",
  "$env:LOCALAPPDATA\Programs\Quarto\bin\quarto.cmd",
  "C:\Program Files\Quarto\bin\quarto.cmd"
)
$quartoLong = $quartoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $quartoLong) { throw "No quarto.cmd found in known locations." }

$rscriptCandidates = @(
  "C:\Program Files\R\R-4.6.0\bin\Rscript.exe",
  "C:\Program Files\R\R-4.5.3\bin\Rscript.exe"
)
$rscript = $rscriptCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($rscript) {
  $env:PATH = "$(Split-Path $rscript);$env:PATH"
}

# Resolve 8.3 short paths to dodge the space-in-path bug
$fso = New-Object -ComObject Scripting.FileSystemObject
$quartoShort = $fso.GetFile($quartoLong).ShortPath
$denoLong = Join-Path (Split-Path $quartoLong) "tools\x86_64\deno.exe"
if (-not (Test-Path $denoLong)) { throw "Bundled deno.exe not found at $denoLong" }
$env:QUARTO_DENO = $fso.GetFile($denoLong).ShortPath

Write-Host "Using quarto at $quartoLong" -ForegroundColor Cyan
& $quartoShort render @args
exit $LASTEXITCODE

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $root "dist"
$addonPath = Join-Path $outDir "voz_nativa_do_dosvox-0.2.2.nvda-addon"

if (!(Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

if (Test-Path $addonPath) {
    Remove-Item -LiteralPath $addonPath
}

python (Join-Path $root "build_nvda_addon.py")

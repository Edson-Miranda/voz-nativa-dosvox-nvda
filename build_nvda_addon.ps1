$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
python (Join-Path $root "build_nvda_addon.py")
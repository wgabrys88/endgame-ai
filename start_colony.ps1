# Launch multi-slot colony (shared bus.json)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
python colony.py @args
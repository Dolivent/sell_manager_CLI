$projectRoot = Split-Path -Parent $PSScriptRoot
$srcPath = Join-Path $projectRoot 'src'

# Set PYTHONPATH for this session and run module
$env:PYTHONPATH = $srcPath
Write-Host "Running sellmanagement with PYTHONPATH=$env:PYTHONPATH"
python -m sellmanagement @args



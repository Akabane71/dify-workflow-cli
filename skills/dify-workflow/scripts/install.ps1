param(
    [string]$ProjectPath = "."
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python is required but was not found in PATH."
}

Push-Location $ProjectPath
try {
    python -m pip install -e .
    python -m pip show dify-ai-workflow-tools
}
finally {
    Pop-Location
}

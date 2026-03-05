# Build the Exegol Sandbox MCP Docker image
# Run from project root: .\build_sandbox.ps1
# The Coder agent runs inside this container for isolated file ops, bash, and pytest.

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "Building Exegol Sandbox MCP image..." -ForegroundColor Cyan
docker build -f "$ProjectRoot\Dockerfile.sandbox" -t exegol-sandbox-mcp:latest "$ProjectRoot"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed." -ForegroundColor Red
    exit 1
}
Write-Host "Sandbox image built: exegol-sandbox-mcp:latest" -ForegroundColor Green
Write-Host "The Coder will use this image for sandboxed execution." -ForegroundColor Gray

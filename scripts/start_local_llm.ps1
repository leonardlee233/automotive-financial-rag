$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimePath = Join-Path $projectRoot 'work/models/llama-cpu/llama-server.exe'
$modelPath = Join-Path $projectRoot 'work/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
if (!(Test-Path -LiteralPath $runtimePath) -or !(Test-Path -LiteralPath $modelPath)) {
    throw 'Run python scripts/setup_local_models.py first.'
}
# Loopback only: never expose a no-auth model service on the local network.
& $runtimePath -m $modelPath --host 127.0.0.1 --port 8081 -c 32768 -t 4 -tb 4 -np 1 --jinja --cache-ram 0

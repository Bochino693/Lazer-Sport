param(
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
Set-Location $ProjectRoot

if (-not (Test-Path ".git")) {
    throw "Execute este script na raiz do repositorio Lazer-Sport."
}

$goodCommit = "0290a8d3c36a59089c1a51b1310680b8c741f2a3"
$files = @(
    "core/context_processors.py",
    "core/views.py",
    "core/templates/home.html"
)

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " LAZER SPORT - RECUPERACAO ERRO 500" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Commit conhecido anterior ao erro:" -ForegroundColor Yellow
Write-Host "  $goodCommit"
Write-Host ""

# Confirma que o commit existe no repositorio local.
git cat-file -e "$goodCommit^{commit}"
if ($LASTEXITCODE -ne 0) {
    throw "O commit $goodCommit nao existe no repositorio local."
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path (Split-Path -Parent $ProjectRoot) ("Lazer-Sport_backup_erro500_" + $stamp)
New-Item -ItemType Directory -Path $backup -Force | Out-Null

foreach ($file in $files) {
    $src = Join-Path $ProjectRoot $file
    if (Test-Path $src) {
        $safe = $file -replace '[\\/:*?"<>|]', '_'
        Copy-Item -LiteralPath $src -Destination (Join-Path $backup $safe) -Force
    }
}

Write-Host "Backup criado:" -ForegroundColor Green
Write-Host "  $backup"
Write-Host ""

Write-Host "Restaurando somente os 3 arquivos alterados..." -ForegroundColor Yellow

git restore --source=$goodCommit -- `
    core/context_processors.py `
    core/views.py `
    core/templates/home.html

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao restaurar os arquivos pelo Git."
}

Write-Host ""
Write-Host "Arquivos restaurados." -ForegroundColor Green
Write-Host ""

# Verificacao objetiva do erro que foi introduzido.
$settings = Get-Content "lazer/settings.py" -Raw
$ctx = Get-Content "core/context_processors.py" -Raw

if ($settings -match "core\.context_processors\.clientes_rodape") {
    if ($ctx -notmatch "def\s+clientes_rodape\s*\(") {
        throw "RECUPERACAO INCOMPLETA: settings.py exige clientes_rodape, mas a funcao nao existe."
    }
}

Write-Host "clientes_rodape: OK" -ForegroundColor Green

Write-Host ""
Write-Host "Executando python manage.py check..." -ForegroundColor Yellow

python manage.py check

if ($LASTEXITCODE -ne 0) {
    throw "Django ainda encontrou erro. Veja a mensagem acima."
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host " RECUPERACAO CONCLUIDA - DJANGO CHECK OK" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Agora rode:" -ForegroundColor Cyan
Write-Host "  python manage.py runserver"
Write-Host ""
Write-Host "Se estiver correto, depois versione a recuperacao:"
Write-Host '  git add core/context_processors.py core/views.py core/templates/home.html'
Write-Host '  git commit -m "reverte otimizacao que causou erro 500"'
Write-Host '  git push'
Write-Host ""

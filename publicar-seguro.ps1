[CmdletBinding()]
param(
    [switch]$MigrarLocal,
    [switch]$Publicar,
    [switch]$PularTestes,
    [string]$Mensagem = "atualiza sistema e migrations"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Escrever-Etapa {
    param([string]$Texto)
    Write-Host ""
    Write-Host "==> $Texto" -ForegroundColor Cyan
}

function Executar {
    param(
        [string]$Descricao,
        [string]$Programa,
        [string[]]$Argumentos
    )

    Escrever-Etapa $Descricao
    & $Programa @Argumentos
    if ($LASTEXITCODE -ne 0) {
        throw "Falhou: $Descricao (codigo $LASTEXITCODE). Nada foi publicado."
    }
}

try {
    $Raiz = $PSScriptRoot
    if (-not $Raiz) {
        $Raiz = (Get-Location).Path
    }
    Set-Location -LiteralPath $Raiz

    if (-not (Test-Path -LiteralPath (Join-Path $Raiz "manage.py"))) {
        throw "manage.py nao encontrado. Coloque este script na raiz do projeto."
    }

    $PythonVenv = Join-Path $Raiz ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $PythonVenv) {
        $Python = $PythonVenv
    }
    else {
        $ComandoPython = Get-Command python -ErrorAction SilentlyContinue
        if (-not $ComandoPython) {
            throw "Python nao encontrado. Ative a .venv ou instale o Python."
        }
        $Python = $ComandoPython.Source
    }

    $ComandoGit = Get-Command git -ErrorAction SilentlyContinue
    if (-not $ComandoGit) {
        throw "Git nao encontrado no PATH."
    }
    $Git = $ComandoGit.Source

    $CoreEsperada = "0103_cupom_data_expiracao_cupom_reutilizavel_and_more.py"
    $InternaEsperada = "0010_ordemproducao_colaborador_alter_ordemproducao_status_and_more.py"
    $PastaCore = Join-Path $Raiz "core\migrations"
    $PastaInterna = Join-Path $Raiz "sistema_interno\migrations"
    $CoreEncontradas = @(Get-ChildItem -LiteralPath $PastaCore -Filter "0103*.py" -File)
    $InternasEncontradas = @(Get-ChildItem -LiteralPath $PastaInterna -Filter "0010*.py" -File)

    if ($CoreEncontradas.Count -ne 1 -or $CoreEncontradas[0].Name -ne $CoreEsperada) {
        $Nomes = ($CoreEncontradas | ForEach-Object Name) -join ", "
        throw "A pasta core\migrations precisa ter somente $CoreEsperada. Encontrado: $Nomes"
    }
    if ($InternasEncontradas.Count -ne 1 -or $InternasEncontradas[0].Name -ne $InternaEsperada) {
        $Nomes = ($InternasEncontradas | ForEach-Object Name) -join ", "
        throw "A pasta sistema_interno\migrations precisa ter somente $InternaEsperada. Encontrado: $Nomes"
    }

    $ConteudoCore = Get-Content -LiteralPath $CoreEncontradas[0].FullName -Raw
    if ($ConteudoCore -notmatch "garantir_colunas_cupom") {
        throw "A core.0103 ainda e a versao antiga. Substitua pela migracao idempotente corrigida."
    }

    Executar "Verificando configuracao do Django" $Python @(
        "manage.py", "check", "--settings=lazer.settings_test"
    )
    Executar "Conferindo se faltam migrations" $Python @(
        "manage.py", "makemigrations", "core", "sistema_interno",
        "--check", "--dry-run", "--settings=lazer.settings_test"
    )
    Executar "Conferindo espacos e conflitos no diff" $Git @("diff", "--check")

    if ($MigrarLocal) {
        Escrever-Etapa "Banco configurado no ambiente local"
        & $Python "manage.py" "shell" "-c" (
            "from django.conf import settings; " +
            "d=settings.DATABASES['default']; " +
            "print('HOST:', d.get('HOST')); print('BANCO:', d.get('NAME'))"
        )
        if ($LASTEXITCODE -ne 0) {
            throw "Nao foi possivel identificar o banco local."
        }

        Write-Host "ATENCAO: confirme que este NAO e o banco de producao." -ForegroundColor Yellow
        $Confirmacao = Read-Host "Digite MIGRAR para aplicar as migrations nesse banco"
        if ($Confirmacao -cne "MIGRAR") {
            throw "Migracao local cancelada pelo usuario."
        }

        Executar "Mostrando o plano de migrations" $Python @("manage.py", "migrate", "--plan")
        Executar "Aplicando migrations no banco local" $Python @("manage.py", "migrate", "--noinput")
        Executar "Conferindo migrations aplicadas" $Python @(
            "manage.py", "showmigrations", "core", "sistema_interno"
        )
    }

    if (-not $PularTestes) {
        Executar "Executando testes em banco temporario isolado" $Python @(
            "manage.py", "test", "sistema_interno", "--verbosity", "1",
            "--settings=lazer.settings_test"
        )
    }

    if (-not $Publicar) {
        Write-Host ""
        Write-Host "Validacao concluida. Nenhum commit ou push foi feito." -ForegroundColor Green
        Write-Host "Para publicar: .\publicar-seguro.ps1 -Publicar -Mensagem `"sua mensagem`""
        exit 0
    }

    $Branch = (& $Git "branch" "--show-current").Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Nao foi possivel identificar a branch atual."
    }
    if ($Branch -ne "main") {
        throw "Publicacao bloqueada: a branch atual e '$Branch'. Troque para main primeiro."
    }

    $EnvVersionado = @(
        & $Git "ls-files" ".env" ".env.*" |
            Where-Object { $_ -ne ".env.example" }
    )
    if ($EnvVersionado.Count -gt 0) {
        throw (
            "Arquivo de ambiente versionado pelo Git: " +
            ($EnvVersionado -join ", ") +
            ". Remova-o do indice antes de publicar para nao vazar senhas."
        )
    }

    Executar "Atualizando referencias do GitHub" $Git @("fetch", "origin")
    Executar "Adicionando alteracoes ao commit" $Git @("add", "-A")

    & $Git "diff" "--cached" "--quiet"
    $TemAlteracoes = $LASTEXITCODE -eq 1
    if ($LASTEXITCODE -gt 1) {
        throw "Nao foi possivel conferir as alteracoes preparadas."
    }

    if ($TemAlteracoes) {
        Executar "Criando commit" $Git @("commit", "-m", $Mensagem)
    }
    else {
        Write-Host "Nenhuma alteracao nova para criar commit." -ForegroundColor Yellow
    }

    Executar "Integrando a main remota" $Git @("pull", "--rebase", "origin", "main")
    Executar "Enviando a main para o GitHub" $Git @("push", "origin", "main")

    Write-Host ""
    Write-Host "Publicacao enviada com sucesso." -ForegroundColor Green
    Write-Host "Com o Pre-Deploy Command configurado no Render, o migrate sera automatico."
}
catch {
    Write-Host ""
    Write-Host "ERRO: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "O script foi interrompido para evitar uma publicacao incompleta." -ForegroundColor Yellow
    exit 1
}

# Correção V17 — cálculo monetário da O.S.

Pacote cumulativo preparado sobre o commit `bee10e2`. Ele contém as
correções das versões V15 e V16 e pode ser copiado por cima delas.

## Aplicar

1. Feche o servidor Django local.
2. Extraia o ZIP.
3. Copie **todo o conteúdo extraído** para a raiz de `Lazer-Sport` e aceite
   substituir os arquivos.
4. Não use `git stash pop`: os stashes existentes pertencem a pacotes
   anteriores.
5. Com a `.venv` ativa, execute:

```powershell
python manage.py migrate
python manage.py check
git status --short
```

Depois de conferir localmente:

```powershell
git add LEIA-ME-CORRECAO-V17.md core/middleware.py sistema_interno
git commit -m "Corrige cálculo monetário dos itens da OS"
git push origin main
```

## O que mudou nesta versão

- O valor unitário criado dinamicamente na linha da O.S. agora recebe a
  máscara monetária compartilhada pelo sistema.
- A digitação acompanha centavos: `4` vira `0,04`, `40` vira `0,40` e `400`
  vira `4,00`.
- O subtotal é recalculado depois que o campo já está formatado, impedindo
  que `400` seja somado como R$ 400,00 quando a intenção era R$ 4,00.
- O campo mostra o prefixo `R$` e mantém o alinhamento da grade para serviço,
  deslocamento, outro e peça/material.
- Preços trazidos pelo catálogo são tratados como valores completos: R$ 40,00
  continua R$ 40,00, sem virar R$ 0,40.
- A declaração duplicada de `AceiteOrcamento` foi removida. O aviso
  `Model 'sistema_interno.aceiteorcamento' was already registered` deixa de
  aparecer, sem mudança no banco e sem perda de dados.

## Verificação

- `manage.py check`: sem problemas e sem o aviso de modelo duplicado.
- `makemigrations --check --dry-run`: nenhuma migração faltando.
- Testes dos fluxos de O.S., orçamento, interface e recuperação de conexão:
  aprovados.
- JavaScript e diferenças do Git passaram nas verificações de sintaxe.

As migrações `0037` e `0038` continuam no pacote porque ele é cumulativo. Se
já foram aplicadas, `migrate` apenas informa que não há nova migração.

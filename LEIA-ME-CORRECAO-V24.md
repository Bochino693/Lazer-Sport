# Correção V24 — impressão limpa e contador dinâmico de O.S.

Pacote cumulativo preparado sobre o commit `bee10e2`. Contém todas as
correções das versões V15 a V23 e pode ser copiado diretamente sobre o
projeto atualizado.

## Aplicar

1. Feche o servidor Django local.
2. Extraia o ZIP.
3. Copie **todo o conteúdo extraído** para a raiz de `Lazer-Sport` e aceite
   substituir os arquivos.
4. Não use `git stash pop`.
5. Com a `.venv` ativa, execute:

```powershell
python manage.py migrate
python manage.py check
git status --short
```

Depois de conferir localmente:

```powershell
git add LEIA-ME-CORRECAO-V24.md core/middleware.py core/templates/gestao core/views.py sistema_interno
git commit -m "Corrige impressão de etiquetas e contador de OS"
git push origin main
```

## Etiqueta sem menu no papel

O modo de impressão agora remove explicitamente:

- menu lateral;
- barra superior;
- formulário da etiqueta;
- barra inferior de atalhos (`.ls-abas`);
- overlay do menu móvel;
- botões flutuantes e carregadores.

Somente as etiquetas permanecem na folha.

## Número das Ordens de Serviço

O contador do menu representa toda O.S. atual ainda não finalizada:

- rascunho: conta;
- aguardando ciência: conta;
- aberta, agendada ou em execução: conta;
- aguardando peça: conta;
- concluída, cancelada ou substituída: não conta;
- v1, v2 ou v3 da mesma O.S.: somente a versão atual conta.

Assim, duas O.S. visíveis e ainda pendentes produzem o número `2`, mesmo que
uma delas ainda seja rascunho.

## Atualização entre usuários

O endpoint de avisos usa uma revisão curta derivada do total e da última
alteração das O.S. no banco. Uma criação, mudança de situação ou exclusão
invalida o cache também entre workers do Render. O painel aberto por outro
usuário atualiza o número no próximo pulso, sem recarregar a página, e o
próprio salvamento solicita uma atualização imediata.

## Modais de clientes

A correção da V23 permanece incluída: o fundo ofuscado fica atrás do cartão,
os campos continuam visíveis e os cliques alcançam a janela.

## Verificação

- `manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: nenhuma migração faltando.
- Testes específicos para impressão, versões e atualização ao vivo.
- 629 testes da suíte completa: aprovados.

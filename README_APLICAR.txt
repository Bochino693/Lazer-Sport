INTERNO VISUAL V3 — REFATORAÇÃO ESTRUTURAL
=========================================

Esta versão NÃO é apenas um tema aplicado sobre o Bootstrap.
As telas principais foram reconstruídas com componentes próprios.

ARQUIVOS:
- sistema_interno/static/interno/interno_modern.css
- sistema_interno/templates/base_inner.html
- sistema_interno/templates/home_inner.html
- sistema_interno/templates/dashboard_estoque.html
- sistema_interno/templates/estoque_inner.html
- sistema_interno/templates/material_inner.html
- sistema_interno/templates/saidas_estoque.html
- sistema_interno/templates/vendas_inner.html
- sistema_interno/templates/pedidos_inner.html
- sistema_interno/templates/manutencao_inner.html
- sistema_interno/templates/login_inner.html
- sistema_interno/templates/logout_inner.html

MANTIDO:
- IDs dos formulários.
- Names dos campos.
- Actions POST.
- painel.js.
- JavaScript de estoque.
- JavaScript de materiais.
- Views, models e URLs.
- Regras de negócio.

MUDANÇAS VISUAIS:
- fundo grafite/azul-marinho real;
- praticamente nenhum painel branco;
- hierarquia de superfície em 3 níveis;
- hero/header grande por tela;
- KPIs altos e legíveis;
- fonte maior;
- tabelas com maior altura e contraste;
- filtros separados visualmente;
- botões maiores;
- modais completamente escuros;
- status por cor;
- navegação maior;
- mobile mais legível;
- cache-busting do CSS com ?v=3.1.

APLICAR SEMPRE NA MAIN:

git switch main
git pull origin main

git add sistema_interno/static/interno/interno_modern.css
git add sistema_interno/templates/base_inner.html
git add sistema_interno/templates/home_inner.html
git add sistema_interno/templates/dashboard_estoque.html
git add sistema_interno/templates/estoque_inner.html
git add sistema_interno/templates/material_inner.html
git add sistema_interno/templates/saidas_estoque.html
git add sistema_interno/templates/vendas_inner.html
git add sistema_interno/templates/pedidos_inner.html
git add sistema_interno/templates/manutencao_inner.html
git add sistema_interno/templates/login_inner.html
git add sistema_interno/templates/logout_inner.html

git diff --check
git status --short
git commit -m "evolui design completo do sistema interno"
git push origin main

Não precisa makemigrations nem migrate.

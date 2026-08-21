# Reparo do ADM — Pedidos + imagens tipadas de brinquedos

Base analisada: `Bochino693/Lazer-Sport`, commit `c6e52e09ecebf7a4f3eca7b3513cb11aeb1364a7`.

## O que este pacote faz

### Pedidos
- corrige o template para herdar `gestao/base_adm.html`;
- moderniza a tela `/adm/pedidos/`;
- mantém filtros por impressão, pagamento e status;
- usa `Pedido.valor_frete`, o snapshot salvo no pedido;
- deixa de depender de `carrinho_origem.valor_frete`;
- mostra os itens e os totais históricos em modal;
- adiciona indicadores de total, aguardando pagamento, pagos e não impressos.

### Brinquedos — imagens
Passam a existir quatro tipos possíveis:
- `perfil`: Perfil / Frente — obrigatória e sempre a capa;
- `verso`: Verso / Costas;
- `lado_direito`: Lado direito;
- `lado_esquerdo`: Lado esquerdo.

Cada brinquedo pode ter no máximo **3 imagens**:
- PERFIL é obrigatória;
- escolha no máximo 2 entre as outras 3 vistas.

O editor do `/adm/brinquedos/` mostra quatro slots visuais e bloqueia uma quarta imagem.

### Capa / requisições
`Brinquedos.imagem_catalogo` passa a significar a imagem `perfil`.

Também são adaptados:
- API de lista de brinquedos;
- API de detalhe de brinquedo;
- promoção que herda imagem do brinquedo;
- loja;
- busca;
- thumbnail do painel administrativo.

Assim as requisições deixam de escolher “a primeira foto” e passam a usar a foto semanticamente marcada como PERFIL.

## Migration

É criada:

`core/migrations/0099_imagembrinquedo_tipo.py`

Para dados existentes:
- 1ª foto atual -> PERFIL;
- 2ª -> VERSO;
- 3ª -> LADO DIREITO;
- fotos antigas excedentes não são apagadas automaticamente, mas ficam fora da galeria moderna até revisão.

Isso evita apagar arquivos antigos durante a migração.

## Como aplicar

Extraia este pacote em qualquer pasta FORA do repositório.

Com o terminal na raiz do projeto:

```powershell
python "CAMINHO\DO\PACOTE\APLICAR_REPARO_ADM.py" .
```

O aplicador:
1. faz backup em `%TEMP%`;
2. altera os arquivos Python;
3. substitui os dois templates;
4. cria a migration 0099;
5. valida sintaxe Python;
6. executa `python manage.py check`;
7. não executa migration, commit ou push.

Depois:

```powershell
python manage.py migrate
python manage.py runserver
```

Teste:
- `/adm/pedidos/`
- `/adm/brinquedos/`
- `/api/v1/brinquedos/`

Depois confira:

```powershell
git diff --check
git status
```

Se estiver tudo correto, adicione somente os arquivos desta alteração:

```powershell
git add core/models.py `
        core/views.py `
        core/api/views.py `
        core/api/serializer.py `
        core/templates/gestao/pedidos_adm.html `
        core/templates/gestao/brinquedos_adm.html `
        core/migrations/0099_imagembrinquedo_tipo.py
```

Então:

```powershell
git commit -m "refatora pedidos e imagens de brinquedos"
git push
```

## Backup

O aplicador informa na tela o caminho exato do backup criado em `%TEMP%`.

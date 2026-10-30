# Brinquedão Modelo 2 — o objeto 3D

O `.glb` que a Arena 3D usa (`core/static/site/arena/modelos/brinquedao-modelo-2.glb`)
sai daqui. Ele junta duas fontes:

1. **O `.3ds` da fábrica** — só a estrutura: colunas (bege), barras e tubos
   verdes e a rede do andar das bolas, em milímetros. O arquivo original tem
   ~280 mil faces (cada tubo com 1.416); aqui ele vira uma lista de colunas e
   barras (`estrutura.json`, feito pelo `extrair.py`) e cada peça é refeita
   leve, no mesmo lugar e na mesma medida.
2. **As imagens do projeto e a planta** (11 m × 2 m, altura 3,5 m) — tudo o
   que o `.3ds` não tem: as três casinhas com arco, o escorregador duplo, o
   tobogã em espiral, as bolas, os pisos, a rede de escalada, o rolo, o tubo
   de passagem, o saco, os painéis com o X e as telas de proteção
   (`montar.js`, peça por peça, encaixadas na grade das colunas).

Medidas finais do objeto (com escorregadores e colchões): 11,4 m × 3,62 m,
altura 3,65 m; ~35 mil triângulos; ~580 KB depois do `gltfpack`.

## Refazer

    python3 extrair.py caminho/do/arquivo.3ds     # estrutura.json
    npm install three@0.169.0 playwright gltfpack
    python3 -m http.server 8790 --bind 127.0.0.1  # nesta pasta
    node gerar.cjs glb                             # vistas v-*.jpg e o .glb
    npx gltfpack -i brinquedao-modelo-2.glb -o ../../../core/static/site/arena/modelos/brinquedao-modelo-2.glb -kn -km

O `.3ds` original (11 MB) não fica no repositório: o que se usa dele está no
`estrutura.json`.

## Ligar no site

`core/arena.py`, `MODELOS_3D`: o objeto se liga à máquina pelo nome
("Brinquedão Modelo 2") e aparece na Arena mesmo antes do cadastro. O
cadastro com as fotos 2D (`static/site/arena/modelos/brinquedao-modelo-2/`)
sai sozinho no deploy, pela migração `core/0113_brinquedao_modelo_2`; se
ela não conseguir, `python manage.py cadastrar_brinquedao_modelo_2`.

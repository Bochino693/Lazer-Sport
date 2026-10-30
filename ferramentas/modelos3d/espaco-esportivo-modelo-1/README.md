# Espaço Esportivo Modelo 1 — o objeto 3D

O `.glb` que a Arena 3D usa (`core/static/site/arena/modelos/espaco-esportivo-modelo-1.glb`)
e as fotos do cadastro (`.../espaco-esportivo-modelo-1/*.webp`) saem daqui.

## De onde vem cada parte

- **`trampo.3ds` da fábrica** (o parque de trampolins). O arquivo traz só a
  estrutura, toda numa cor: a grade de aço das camas (módulos de ~2,08 m, a
  0,85 m do chão), os postes laranja e o quadro preto de cima (3,65 m) e as
  gaiolas pretas das piscinas de espuma (2,6 m). Daqui saem essas alturas e
  essa estrutura (o `ler_3ds.py` do `../brinquedao-modelo-2/` lista o
  conteúdo de um `.3ds`).
- **A planta do parque (18 m × 16,5 m)**: a divisão das camas e as cores
  dos acolchoados, as seis piscinas de espuma com o percurso suspenso, a
  piscina grande com a parede de escalada, as cinco enterradas com cesta,
  o varredor e as escadas.
- **A planta das quadras (altura 2,90 m)**: campo e quadra de basquete
  enjaulados (8 m + 7 m, por 4 + 4 m), as duas arenas de panna de 5 m e a
  pista de 2 m × 14 m.
- **As imagens do espaço completo**: o piso azul de EVA, os blocos de
  proteção, o circuito kids na frente do parque (pórticos, decks, obstáculos,
  redes) e o tobogã com a piscina de bolinhas.

Tudo junto: 39 m × 23 m, altura de 3,9 m; ~33 mil triângulos; ~720 KB.
As camas levam a marca `lona` (no passeio da Arena, quem pisa nelas quica).

## Refazer

    npm install three@0.169.0 playwright gltfpack
    python3 -m http.server 8790 --bind 127.0.0.1    # nesta pasta
    node gerar.cjs glb fotos                         # vistas, fotos e o .glb
    npx gltfpack -i espaco-esportivo-modelo-1.glb -o ../../../core/static/site/arena/modelos/espaco-esportivo-modelo-1.glb -kn -km -ke

As fotos `foto-*.jpg` viram os `.webp` da pasta do modelo.

## Ligar no site

`core/arena.py`, `MODELOS_3D`: liga pelo nome ("Espaço Esportivo Modelo 1"),
na área "Espaços esportivos", e como `reino` (grande demais para a roda: fica
ao lado dela, ligado por uma passarela). O cadastro com as fotos sai no
deploy pela migração `core/0114_espaco_esportivo_modelo_1`; se ela não
conseguir, `python manage.py cadastrar_modelo_3d espaco-esportivo-modelo-1`.

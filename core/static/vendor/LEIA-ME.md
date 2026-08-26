# Arquivos de terceiros servidos pelo próprio site

Estão aqui, e não em CDN, por um motivo prático: quando o CDN não
responde -- operadora, DNS, rede corporativa --, o site perde todos os
ícones de uma vez e fica no ar parecendo quebrado.

| Pasta | O que é | Versão | Origem |
|---|---|---|---|
| `fontawesome/` | ícones do site | 6.5.1 | npm `@fortawesome/fontawesome-free` |
| `fontes/` + `fontes.css` | Manrope, Poppins, Montserrat, Inter (recorte latino) | fontsource | npm `@fontsource/*` |
| `leaflet/` | mapa de clientes da home | 1.9.4 | npm `leaflet` |

Os arquivos são os oficiais, sem alteração, com uma exceção: do CSS do
Font Awesome foram removidos os `url(...ttf)`, porque só o `woff2` foi
trazido -- é o formato que todo navegador em uso hoje aceita, e referência
para arquivo ausente vira 404 no console de quem for depurar.

O painel interno tem os seus próprios (Bootstrap e Bootstrap Icons) em
`sistema_interno/static/interno/vendor/`.

`core/tests_assets.py` falha se algum template voltar a puxar CSS, fonte
ou script de fora.

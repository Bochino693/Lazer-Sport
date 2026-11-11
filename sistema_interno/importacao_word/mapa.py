"""O cliente importado vira alfinete no mapa da home.

POR QUE ISTO EXISTE. O pedido: "deixe ligado a questão de aparecer no
mapa, pois para preencher rapido o mapa e ficar bem povoado que vamos
fazer essa função". Cadastrar pelo documento é o jeito rápido de pôr
muitos clientes no mapa -- e o mapa só desenha quem tem TRÊS coisas
(ver `HomeView._build_public_context`, em core/views.py):

  * `Cliente.publicar_no_mapa` ligado (a chave "Aparecer no mapa do
    site" da conferência, que vem ligada) e o cadastro ativo;
  * um endereço (`EnderecoCliente`, o primeiro do cliente);
  * a COORDENADA desse endereço (latitude e longitude).

A coordenada é a parte que o documento não traz. O cadastro à mão a
consegue no navegador, pela mesma consulta rápida de CEP que está aqui
(`buscar_coordenadas_cep_rapido`: BrasilAPI, uma chamada, poucos
segundos). Quando ela não acha, vale o que o painel já tinha para
"Recalcular localização": `EnderecoCliente.localizar()` -- o CEP e o
número no Nominatim (OpenStreetMap), e por fim o centro da cidade.
Nenhum serviço novo, nada pago.

FORA DA GRAVAÇÃO, SEMPRE. Isto roda depois que o cliente já foi salvo
(e fora da transação): consulta a serviço de fora não pode prender nem
desfazer o cadastro que a pessoa acabou de conferir. Se nada achar o
endereço, o cliente fica cadastrado do mesmo jeito, marcado para o mapa,
e a tela final diz "não achei o endereço no mapa: confira" com o caminho
para a ficha.
"""

from __future__ import annotations

import logging

from core.home_cache import invalidate_home_cache
from core.utils import buscar_coordenadas_cep_rapido

from ..models import Cliente, EnderecoCliente

logger = logging.getLogger(__name__)

SEM_ENDERECO = "o documento não traz o endereço do cliente, e sem ele não há alfinete"
NAO_ACHEI = "não achei o endereço no mapa: confira o CEP e a cidade na ficha do cliente"
ARQUIVADO = "o cadastro está arquivado (inativo), e cadastro arquivado não aparece no mapa"


def _onde(endereco: EnderecoCliente | None) -> str:
    return endereco.linha_curta if endereco else ""


def procurar_coordenadas(endereco: EnderecoCliente):
    """(latitude, longitude, precisão) do endereço, ou (None, None, "").

    Primeiro a consulta rápida do CEP -- a mesma do cadastro à mão. A
    precisão dela não é conhecida (é o ponto do CEP), então fica em
    branco: o `conferir_mapa` sabe refinar depois. Sem resposta, o
    caminho completo do painel (`localizar`), que já devolve a precisão.
    """
    if endereco.cep:
        latitude, longitude = buscar_coordenadas_cep_rapido(endereco.cep)
        if latitude is not None and longitude is not None:
            return latitude, longitude, ""
    if endereco.localizar():
        return endereco.latitude, endereco.longitude, endereco.precisao
    return None, None, ""


def colocar_no_mapa(cliente: Cliente) -> dict:
    """Garante o alfinete de um cliente marcado para o mapa.

    Devolve o que a tela final mostra: {"marcado", "no_mapa", "onde",
    "motivo", "ja_estava"}. Nunca levanta: um erro de rede vira "não
    achei", e o cliente continua cadastrado.
    """
    cliente = Cliente.objects.get(pk=cliente.pk)
    endereco = cliente.enderecos.order_by("id").first()
    resultado = {"marcado": cliente.publicar_no_mapa, "no_mapa": False, "onde": _onde(endereco),
                 "motivo": "", "ja_estava": False}
    if not cliente.publicar_no_mapa:
        return resultado
    if not cliente.ativo:
        resultado["motivo"] = ARQUIVADO
        return resultado
    if endereco is None:
        resultado["motivo"] = SEM_ENDERECO
        return resultado
    if endereco.tem_local:
        resultado.update(no_mapa=True, ja_estava=True)
        invalidate_home_cache()
        return resultado

    try:
        latitude, longitude, precisao = procurar_coordenadas(endereco)
    except Exception:  # noqa: BLE001 -- serviço de fora: nada aqui derruba o cadastro
        logger.exception("[MAPA] Importação: não deu para localizar o endereço do cliente %s.", cliente.pk)
        latitude = longitude = None
        precisao = ""
    if latitude is None or longitude is None:
        logger.info("[MAPA] Importação: endereço do cliente %s sem coordenada (%s).", cliente.pk, _onde(endereco))
        resultado["motivo"] = NAO_ACHEI
        return resultado

    endereco.latitude = latitude
    endereco.longitude = longitude
    endereco.precisao = precisao or ""
    endereco.save(update_fields=["latitude", "longitude", "precisao"])
    # A home guarda o mapa em cache por até meia hora. Quem acabou de
    # cadastrar quer ver o alfinete agora, e não daqui a trinta minutos.
    invalidate_home_cache()
    resultado["no_mapa"] = True
    return resultado

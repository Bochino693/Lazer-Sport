"""Distância aproximada e atalhos de rota para Clientes e O.S.

O painel não tenta substituir o roteador: a distância exibida é em linha
reta e os links entregam origem/destino ao Google Maps ou Waze, que então
calculam trânsito, vias e tempo real.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from urllib.parse import urlencode

from core.models import EnderecoEmpresa


def _decimal(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def texto_endereco(endereco) -> str:
    if not endereco:
        return ""
    rua = getattr(endereco, "endereco", None) or getattr(endereco, "rua", "")
    partes = [
        ", ".join(p for p in (rua, getattr(endereco, "numero", "")) if p),
        getattr(endereco, "bairro", ""),
        "/".join(
            p for p in (
                getattr(endereco, "cidade", ""),
                getattr(endereco, "estado", ""),
            ) if p
        ),
        f"CEP {getattr(endereco, 'cep', '')}" if getattr(endereco, "cep", "") else "",
    ]
    return " · ".join(p for p in partes if p)


def origem_empresa() -> dict:
    empresa = EnderecoEmpresa.objects.order_by("id").first()
    if not empresa:
        return {"latitude": None, "longitude": None, "endereco": ""}
    return {
        "latitude": _decimal(empresa.latitude),
        "longitude": _decimal(empresa.longitude),
        "endereco": texto_endereco(empresa),
    }


def distancia_em_linha_reta(origem: dict, latitude, longitude):
    lat1 = _decimal(origem.get("latitude"))
    lon1 = _decimal(origem.get("longitude"))
    lat2 = _decimal(latitude)
    lon2 = _decimal(longitude)
    if None in (lat1, lon1, lat2, lon2):
        return None
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    a = min(1, max(0, a))
    return round(6371.0088 * 2 * asin(sqrt(a)), 1)


def dados_rota(*, destino_texto="", destino=None, origem=None) -> dict:
    origem = origem or origem_empresa()
    latitude = getattr(destino, "latitude", None) if destino else None
    longitude = getattr(destino, "longitude", None) if destino else None
    destino_texto = destino_texto or texto_endereco(destino)
    coordenada = (
        f"{latitude},{longitude}"
        if latitude is not None and longitude is not None
        else ""
    )
    alvo = coordenada or destino_texto
    if not alvo:
        return {"google_maps_url": "", "waze_url": "", "distancia_km": None}

    parametros_google = {
        "api": "1",
        "destination": alvo,
        "travelmode": "driving",
    }
    origem_coordenada = ""
    if origem.get("latitude") is not None and origem.get("longitude") is not None:
        origem_coordenada = f"{origem['latitude']},{origem['longitude']}"
    elif origem.get("endereco"):
        origem_coordenada = origem["endereco"]
    if origem_coordenada:
        parametros_google["origin"] = origem_coordenada

    parametros_waze = {"navigate": "yes"}
    parametros_waze["ll" if coordenada else "q"] = alvo
    return {
        "google_maps_url": "https://www.google.com/maps/dir/?" + urlencode(parametros_google),
        "waze_url": "https://waze.com/ul?" + urlencode(parametros_waze),
        "distancia_km": distancia_em_linha_reta(origem, latitude, longitude),
    }

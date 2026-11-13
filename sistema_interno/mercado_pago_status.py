"""Situação das credenciais do Mercado Pago, para o gestor conferir no painel.

As chaves ficam só nas variáveis do Render. Esta tela responde a pergunta
"estou recebendo de verdade ou em modo de teste?" sem nunca exibir a chave:
mostra o tipo (produção ou teste), os últimos quatro caracteres para
conferir com o painel do Mercado Pago, e se a conta aceitou o token.

A conta é consultada em ``/users/me`` com tempo curto e resultado guardado
por alguns minutos, para o Financeiro abrir rápido mesmo se a API demorar.
"""

import hashlib
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

URL_CONTA = "https://api.mercadopago.com/users/me"
TEMPO_LIMITE = 3
GUARDAR_OK = 10 * 60
GUARDAR_FALHA = 60


def tipo_da_chave(valor):
    valor = (valor or "").strip()
    if not valor:
        return "vazia"
    if valor.upper().startswith("TEST-"):
        return "teste"
    if valor.upper().startswith("APP_USR-"):
        return "producao"
    return "desconhecida"


def final_da_chave(valor):
    valor = (valor or "").strip()
    return f"…{valor[-4:]}" if len(valor) >= 8 else ""


def consultar_conta(token):
    """Pergunta ao Mercado Pago de quem é o token. Nunca levanta exceção."""
    chave = "mp-conta-" + hashlib.sha256(token.encode()).hexdigest()[:24]
    guardado = cache.get(chave)
    if guardado is not None:
        return guardado

    try:
        resposta = requests.get(
            URL_CONTA,
            headers={"Authorization": f"Bearer {token}"},
            timeout=TEMPO_LIMITE,
        )
    except requests.RequestException as erro:
        logger.warning("Mercado Pago não respondeu à conferência da conta: %s", erro)
        conta = {"estado": "sem_resposta"}
        cache.set(chave, conta, GUARDAR_FALHA)
        return conta

    if resposta.status_code == 401:
        conta = {"estado": "recusado"}
    elif resposta.status_code != 200:
        conta = {"estado": "sem_resposta"}
    else:
        try:
            dados = resposta.json()
        except ValueError:
            dados = {}
        etiquetas = [str(t).lower() for t in (dados.get("tags") or [])]
        conta = {
            "estado": "aceito",
            "usuario_de_teste": "test_user" in etiquetas,
            "pais": dados.get("site_id") or "",
        }

    cache.set(chave, conta, GUARDAR_OK if conta["estado"] == "aceito" else GUARDAR_FALHA)
    return conta


def situacao_mercado_pago(consultar=True):
    token = getattr(settings, "MP_ACCESS_TOKEN", "") or ""
    publica = getattr(settings, "MP_PUBLIC_KEY", "") or ""
    tipo_token = tipo_da_chave(token)
    tipo_publica = tipo_da_chave(publica)

    chaves = [
        {"nome": "MP_ACCESS_TOKEN", "tipo": tipo_token, "final": final_da_chave(token)},
        {"nome": "MP_PUBLIC_KEY", "tipo": tipo_publica, "final": final_da_chave(publica)},
    ]
    avisos = []
    conta = None

    if tipo_token == "vazia" or tipo_publica == "vazia":
        faltando = [c["nome"] for c in chaves if c["tipo"] == "vazia"]
        return {
            "nivel": "erro",
            "modo": "INCOMPLETO",
            "titulo": "Falta configurar " + " e ".join(faltando),
            "resumo": "Sem as duas chaves o cliente não consegue pagar no site.",
            "chaves": chaves,
            "avisos": [],
        }

    if consultar:
        conta = consultar_conta(token)

    if tipo_token == "teste" or tipo_publica == "teste":
        nivel, modo = "alerta", "TESTE"
        titulo = "Credenciais de TESTE"
        resumo = (
            "Pagamentos de teste não caem na sua conta. Cliente de verdade "
            "não consegue pagar: troque pelas credenciais de produção."
        )
    elif conta and conta.get("usuario_de_teste"):
        nivel, modo = "alerta", "TESTE"
        titulo = "Conta de usuário de teste"
        resumo = (
            "As chaves são de uma conta de teste do Mercado Pago. Use as "
            "credenciais de produção da conta da empresa."
        )
    elif tipo_token == "producao" and tipo_publica == "producao":
        nivel, modo = "ok", "PRODUÇÃO"
        titulo = "Recebendo de verdade"
        resumo = "Pix e cartão caem na conta do Mercado Pago da empresa."
    else:
        nivel, modo = "erro", "DESCONHECIDO"
        titulo = "Chave em formato desconhecido"
        resumo = (
            "As chaves do Mercado Pago começam com APP_USR- (produção) ou "
            "TEST- (teste). Confira se colou a chave inteira, sem espaços."
        )

    if tipo_token != tipo_publica and "vazia" not in (tipo_token, tipo_publica):
        avisos.append(
            "O token e a chave pública são de tipos diferentes. As duas "
            "precisam ser de produção, do mesmo aplicativo."
        )

    if conta:
        if conta["estado"] == "recusado":
            nivel = "erro"
            avisos.append(
                "O Mercado Pago recusou o MP_ACCESS_TOKEN. Copie de novo o "
                "Access Token de produção e salve no Render."
            )
        elif conta["estado"] == "sem_resposta":
            avisos.append(
                "Não foi possível falar com o Mercado Pago agora para "
                "confirmar a conta. O tipo das chaves acima continua valendo."
            )
        elif conta.get("pais") and conta["pais"] != "MLB":
            avisos.append(
                f"A conta é de outro país ({conta['pais']}). Para Pix em reais "
                "ela precisa ser do Brasil (MLB)."
            )

    return {
        "nivel": nivel,
        "modo": modo,
        "titulo": titulo,
        "resumo": resumo,
        "chaves": chaves,
        "avisos": avisos,
        "conta_aceita": bool(conta and conta["estado"] == "aceito"),
    }

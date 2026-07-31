import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


load_dotenv()


# ============================================================
# CONFIGURAÇÕES
# ============================================================

FEVER_URL = os.getenv("FEVER_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ARQUIVO_ESTADO = Path("estado.txt")
ARQUIVO_ALERTA_VIDA = Path("ultimo_alerta_vida.txt")

TEXTOS_INDISPONIVEIS = [
    "não há ingressos à venda",
    "nao ha ingressos a venda",
    "assim que estiverem disponíveis, vamos avisá-lo",
    "assim que estiverem disponiveis, vamos avisa-lo",
    "ingressos esgotados",
    "não disponível",
    "nao disponivel",
]

TEXTOS_DE_COMPRA = [
    "selecionar assentos",
    "comprar ingressos",
    "selecionar ingressos",
    "selecione a data e opção",
    "selecione a data e opcao",
    "escolher ingressos",
    "ver ingressos",
]


# ============================================================
# VALIDAÇÃO
# ============================================================

def validar_configuracao() -> None:
    faltando = []

    if not FEVER_URL:
        faltando.append("FEVER_URL")

    if not TELEGRAM_BOT_TOKEN:
        faltando.append("TELEGRAM_BOT_TOKEN")

    if not TELEGRAM_CHAT_ID:
        faltando.append("TELEGRAM_CHAT_ID")

    if faltando:
        nomes = ", ".join(faltando)

        raise RuntimeError(
            f"As seguintes variáveis estão faltando no .env: {nomes}"
        )


# ============================================================
# TEXTO
# ============================================================

def normalizar_texto(texto: str) -> str:
    texto = texto.lower()

    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def contem_algum(texto: str, possibilidades: list[str]) -> bool:
    texto_normalizado = normalizar_texto(texto)

    return any(
        normalizar_texto(possibilidade) in texto_normalizado
        for possibilidade in possibilidades
    )


# ============================================================
# TELEGRAM
# ============================================================

def enviar_telegram(mensagem: str) -> None:
    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    resposta = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    resposta.raise_for_status()

    dados = resposta.json()

    if not dados.get("ok"):
        raise RuntimeError(
            f"O Telegram recusou a mensagem: {dados}"
        )


# ============================================================
# ESTADO
# ============================================================

def carregar_estado_anterior() -> str:
    if not ARQUIVO_ESTADO.exists():
        return "desconhecido"

    try:
        return ARQUIVO_ESTADO.read_text(
            encoding="utf-8"
        ).strip()

    except OSError:
        return "desconhecido"


def salvar_estado(estado: str) -> None:
    ARQUIVO_ESTADO.write_text(
        estado,
        encoding="utf-8",
    )


def carregar_data_ultimo_alerta_vida() -> str:
    if not ARQUIVO_ALERTA_VIDA.exists():
        return ""

    try:
        return ARQUIVO_ALERTA_VIDA.read_text(
            encoding="utf-8"
        ).strip()

    except OSError:
        return ""


def salvar_data_alerta_vida(data: str) -> None:
    ARQUIVO_ALERTA_VIDA.write_text(
        data,
        encoding="utf-8",
    )


def deve_enviar_alerta_vida(data_atual: str) -> bool:
    data_ultimo_alerta = carregar_data_ultimo_alerta_vida()

    return data_ultimo_alerta != data_atual


# ============================================================
# ANÁLISE
# ============================================================

def classificar_pagina(texto: str) -> tuple[str, str]:
    tem_indisponibilidade = contem_algum(
        texto,
        TEXTOS_INDISPONIVEIS,
    )

    tem_compra = contem_algum(
        texto,
        TEXTOS_DE_COMPRA,
    )

    if tem_compra:
        return (
            "disponivel",
            "Foi encontrado um botão ou painel de compra.",
        )

    if tem_indisponibilidade:
        return (
            "indisponivel",
            "A página continua mostrando o aviso de indisponibilidade.",
        )

    return (
        "suspeito",
        "O aviso antigo desapareceu, mas nenhum botão conhecido foi encontrado.",
    )


def obter_texto_da_pagina() -> tuple[str, str]:
    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(
            headless=True
        )

        pagina = navegador.new_page(
            locale="pt-BR",
            viewport={
                "width": 1366,
                "height": 768,
            },
        )

        try:
            resposta = pagina.goto(
                FEVER_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            if resposta is not None and resposta.status >= 400:
                raise RuntimeError(
                    f"A Fever retornou HTTP {resposta.status}."
                )

            pagina.wait_for_timeout(5_000)

            titulo = pagina.title()

            texto = pagina.locator("body").inner_text(
                timeout=20_000
            )

            return titulo, texto

        finally:
            navegador.close()


# ============================================================
# EXECUÇÃO
# ============================================================

def executar() -> None:
    validar_configuracao()

    agora = datetime.now()

    horario = agora.strftime("%d/%m/%Y às %H:%M:%S")
    data_atual = agora.strftime("%d/%m/%Y")

    print("Abrindo a página da Fever...")
    print(FEVER_URL)

    titulo, texto = obter_texto_da_pagina()

    estado_atual, motivo = classificar_pagina(texto)
    estado_anterior = carregar_estado_anterior()

    print()
    print(f"Título: {titulo}")
    print(f"Estado anterior: {estado_anterior}")
    print(f"Estado atual: {estado_atual}")
    print(f"Motivo: {motivo}")

    # ========================================================
    # ALERTA REPETIDO QUANDO HOUVER SINAL DE VENDA
    # ========================================================

    if estado_atual == "disponivel":
        mensagem = (
            "🚨 INGRESSOS POSSIVELMENTE DISPONÍVEIS!\n\n"
            f"{titulo}\n"
            f"{motivo}\n\n"
            f"Verificado em {horario}\n\n"
            f"{FEVER_URL}"
        )

        enviar_telegram(mensagem)

        print("Alerta de disponibilidade enviado.")

    elif estado_atual == "suspeito":
        mensagem = (
            "⚠️ A PÁGINA DA FEVER MUDOU\n\n"
            "O aviso de indisponibilidade desapareceu, "
            "mas o monitor ainda não encontrou um botão "
            "de compra conhecido.\n\n"
            f"Título: {titulo}\n"
            f"Verificado em {horario}\n\n"
            f"{FEVER_URL}"
        )

        enviar_telegram(mensagem)

        print("Alerta de mudança suspeita enviado.")

    else:
        print("Ainda não há sinal de venda.")

    # ========================================================
    # ALERTA DE VIDA UMA VEZ POR DIA
    # ========================================================

    if deve_enviar_alerta_vida(data_atual):
        mensagem_vida = (
            "✅ MONITOR FEVER FUNCIONANDO\n\n"
            "A página foi carregada e analisada com sucesso.\n\n"
            f"Evento: {titulo}\n"
            f"Estado atual: {estado_atual}\n"
            f"Motivo: {motivo}\n"
            f"Verificado em {horario}\n\n"
            f"{FEVER_URL}"
        )

        enviar_telegram(mensagem_vida)
        salvar_data_alerta_vida(data_atual)

        print("Alerta diário de vida enviado.")

    salvar_estado(estado_atual)


if __name__ == "__main__":
    try:
        executar()

    except PlaywrightTimeoutError as erro:
        print(f"Tempo esgotado ao carregar a página: {erro}")
        raise SystemExit(1)

    except requests.RequestException as erro:
        print(f"Erro de internet ou Telegram: {erro}")
        raise SystemExit(1)

    except Exception as erro:
        print(f"Erro inesperado: {erro}")
        raise SystemExit(1)
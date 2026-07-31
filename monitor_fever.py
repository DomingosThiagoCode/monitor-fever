import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")

ARQUIVO_ESTADO = Path("estado.txt")


TEXTOS_INDISPONIVEIS = [
    "não há ingressos à venda",
    "nao ha ingressos a venda",
    "assim que estiverem disponíveis, vamos avisá-lo",
    "assim que estiverem disponiveis, vamos avisa-lo",
    "ingressos esgotados",
    "não disponível",
    "nao disponivel",
    "poxa! adoramos esta experiência",
    "poxa! adoramos esta experiencia",
]


TEXTOS_DE_COMPRA = [
    "selecionar assentos",
    "comprar ingressos",
    "selecionar ingressos",
    "selecione a data e opção",
    "selecione a data e opcao",
    "escolher ingressos",
    "ver ingressos",
    "selecionar data",
    "escolher data",
]


# ============================================================
# VALIDAÇÃO
# ============================================================

def validar_configuracao() -> None:
    faltando: list[str] = []

    if not FEVER_URL:
        faltando.append("FEVER_URL")

    if not TELEGRAM_BOT_TOKEN:
        faltando.append("TELEGRAM_BOT_TOKEN")

    if not TELEGRAM_CHAT_ID:
        faltando.append("TELEGRAM_CHAT_ID")

    if faltando:
        nomes = ", ".join(faltando)

        raise RuntimeError(
            f"As seguintes variáveis estão faltando: {nomes}"
        )


# ============================================================
# TEXTO
# ============================================================

def normalizar_texto(texto: str) -> str:
    texto = texto.lower()

    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()


def contem_algum(
    texto: str,
    possibilidades: list[str],
) -> bool:
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
        "https://api.telegram.org/"
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
        estado = ARQUIVO_ESTADO.read_text(
            encoding="utf-8"
        ).strip()

        return estado or "desconhecido"

    except OSError:
        return "desconhecido"


def salvar_estado(estado: str) -> None:
    try:
        ARQUIVO_ESTADO.write_text(
            estado,
            encoding="utf-8",
        )

    except OSError as erro:
        print(
            "Não foi possível salvar o estado local: "
            f"{erro}"
        )


# ============================================================
# ANÁLISE DA PÁGINA
# ============================================================

def classificar_pagina(
    texto: str,
) -> tuple[str, str]:
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
            "A página continua mostrando o aviso "
            "de indisponibilidade.",
        )

    return (
        "suspeito",
        "O aviso antigo desapareceu, mas nenhum botão "
        "conhecido de compra foi encontrado.",
    )


# ============================================================
# PLAYWRIGHT
# ============================================================

def obter_texto_da_pagina() -> tuple[str, str]:
    if not FEVER_URL:
        raise RuntimeError(
            "A variável FEVER_URL não está configurada."
        )

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        contexto = navegador.new_context(
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            viewport={
                "width": 1366,
                "height": 768,
            },
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0.0.0 "
                "Safari/537.36"
            ),
        )

        pagina = contexto.new_page()

        try:
            resposta = pagina.goto(
                FEVER_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            if (
                resposta is not None
                and resposta.status >= 400
            ):
                raise RuntimeError(
                    "A Fever retornou o código HTTP "
                    f"{resposta.status}."
                )

            pagina.wait_for_timeout(5_000)

            titulo = pagina.title()

            texto = pagina.locator(
                "body"
            ).inner_text(
                timeout=20_000
            )

            if not texto.strip():
                raise RuntimeError(
                    "A página foi aberta, mas nenhum texto "
                    "foi encontrado."
                )

            return titulo, texto

        finally:
            contexto.close()
            navegador.close()


# ============================================================
# ALERTAS
# ============================================================

def enviar_alerta_disponibilidade(
    titulo: str,
    motivo: str,
    horario: str,
) -> None:
    mensagem = (
        "🚨 INGRESSOS POSSIVELMENTE DISPONÍVEIS!\n\n"
        f"Evento: {titulo}\n\n"
        f"{motivo}\n\n"
        f"Verificado em {horario}\n\n"
        f"{FEVER_URL}"
    )

    enviar_telegram(mensagem)

    print("Alerta de disponibilidade enviado.")


def enviar_alerta_suspeito(
    titulo: str,
    motivo: str,
    horario: str,
) -> None:
    mensagem = (
        "⚠️ A PÁGINA DA FEVER MUDOU\n\n"
        "O aviso de indisponibilidade desapareceu, "
        "mas o monitor ainda não encontrou um botão "
        "de compra conhecido.\n\n"
        f"Evento: {titulo}\n"
        f"Motivo: {motivo}\n"
        f"Verificado em {horario}\n\n"
        f"{FEVER_URL}"
    )

    enviar_telegram(mensagem)

    print("Alerta de página suspeita enviado.")


def enviar_alerta_vida(
    titulo: str,
    estado: str,
    motivo: str,
    horario: str,
) -> None:
    mensagem = (
        "✅ MONITOR FEVER FUNCIONANDO\n\n"
        "A página foi carregada e analisada "
        "com sucesso.\n\n"
        f"Evento: {titulo}\n"
        f"Estado atual: {estado}\n"
        f"Motivo: {motivo}\n"
        f"Verificado em {horario}\n\n"
        f"{FEVER_URL}"
    )

    enviar_telegram(mensagem)

    print("Alerta diário de vida enviado.")


def esta_no_horario_do_alerta_vida(
    agora: datetime,
) -> bool:
    return (
        agora.hour == 8
        and 0 <= agora.minute < 5
    )


# ============================================================
# EXECUÇÃO
# ============================================================

def executar() -> None:
    validar_configuracao()

    agora = datetime.now(
        FUSO_HORARIO
    )

    horario = agora.strftime(
        "%d/%m/%Y às %H:%M:%S"
    )

    print("=" * 60)
    print("MONITOR DA FEVER")
    print("=" * 60)
    print(f"Horário: {horario}")
    print("Abrindo a página da Fever...")
    print(FEVER_URL)

    titulo, texto = obter_texto_da_pagina()

    estado_atual, motivo = classificar_pagina(
        texto
    )

    estado_anterior = carregar_estado_anterior()

    print()
    print(f"Título: {titulo}")
    print(f"Estado anterior: {estado_anterior}")
    print(f"Estado atual: {estado_atual}")
    print(f"Motivo: {motivo}")

    # Se houver sinal de venda, envia mensagem
    # em todas as execuções.
    if estado_atual == "disponivel":
        enviar_alerta_disponibilidade(
            titulo=titulo,
            motivo=motivo,
            horario=horario,
        )

    # Se a página mudar de uma maneira inesperada,
    # também envia mensagem em todas as execuções.
    elif estado_atual == "suspeito":
        enviar_alerta_suspeito(
            titulo=titulo,
            motivo=motivo,
            horario=horario,
        )

    else:
        print("Ainda não há sinal de venda.")

    # Com cron a cada 5 minutos, essa condição
    # será verdadeira apenas na execução próxima das 08:00.
    if esta_no_horario_do_alerta_vida(agora):
        enviar_alerta_vida(
            titulo=titulo,
            estado=estado_atual,
            motivo=motivo,
            horario=horario,
        )

    salvar_estado(estado_atual)

    print()
    print("Verificação concluída.")
    print("=" * 60)


# ============================================================
# INICIALIZAÇÃO
# ============================================================

if __name__ == "__main__":
    try:
        executar()

    except PlaywrightTimeoutError as erro:
        print(
            "Tempo esgotado ao carregar a página: "
            f"{erro}"
        )
        raise SystemExit(1)

    except requests.RequestException as erro:
        print(
            "Erro de internet ou Telegram: "
            f"{erro}"
        )
        raise SystemExit(1)

    except Exception as erro:
        print(
            "Erro inesperado: "
            f"{erro}"
        )
        raise SystemExit(1)
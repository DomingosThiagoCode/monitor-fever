import os

import requests
from dotenv import load_dotenv


load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

if not token:
    raise RuntimeError(
        "O TELEGRAM_BOT_TOKEN não foi encontrado no arquivo .env."
    )

if not chat_id:
    raise RuntimeError(
        "O TELEGRAM_CHAT_ID não foi encontrado no arquivo .env."
    )

url = f"https://api.telegram.org/bot{token}/sendMessage"

mensagem = (
    "🤖 Monitor Fever conectado!\n\n"
    "Quando os ingressos aparecerem, o alerta chegará aqui."
)

resposta = requests.post(
    url,
    json={
        "chat_id": chat_id,
        "text": mensagem,
    },
    timeout=20,
)

resposta.raise_for_status()

dados = resposta.json()

if not dados.get("ok"):
    raise RuntimeError(f"Erro retornado pelo Telegram: {dados}")

print("Mensagem enviada com sucesso.")
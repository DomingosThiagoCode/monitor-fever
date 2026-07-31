import os

import requests
from dotenv import load_dotenv


load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")

if not token:
    raise RuntimeError(
        "O TELEGRAM_BOT_TOKEN não foi encontrado no arquivo .env."
    )

url = f"https://api.telegram.org/bot{token}/getUpdates"

resposta = requests.get(url, timeout=20)
resposta.raise_for_status()

dados = resposta.json()

if not dados.get("ok"):
    raise RuntimeError(f"Erro retornado pelo Telegram: {dados}")

resultados = dados.get("result", [])

if not resultados:
    print(
        "Nenhuma mensagem encontrada.\n"
        "Abra o bot no Telegram, envie /start e depois execute novamente."
    )
else:
    for atualizacao in resultados:
        mensagem = atualizacao.get("message", {})
        conversa = mensagem.get("chat", {})

        chat_id = conversa.get("id")
        nome = conversa.get("first_name", "desconhecido")
        texto = mensagem.get("text", "")

        print(f"Nome: {nome}")
        print(f"Chat ID: {chat_id}")
        print(f"Mensagem: {texto}")
        print("-" * 40)
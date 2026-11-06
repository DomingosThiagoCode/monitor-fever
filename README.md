# Monitor de disponibilidade de ingressos — Fever

Automação em Python que verifica uma página de evento da Fever e envia notificações pelo Telegram quando identifica sinais de venda de ingressos ou mudanças inesperadas na página.

## Como funciona

- Acessa a página usando **Playwright**.
- Normaliza e analisa os textos exibidos para classificar o estado da venda.
- Envia alertas ao Telegram quando identifica disponibilidade ou uma situação suspeita.
- Registra o estado da última verificação em `estado.txt`.
- Inclui um alerta periódico de funcionamento próximo das 8h (horário de São Paulo), quando executado nesse intervalo.

## Tecnologias

Python, Playwright, Requests, python-dotenv, Telegram Bot API e Docker.

## Arquivos principais

- `monitor_fever.py`: verificação e envio de alertas.
- `descobrir_chat_id.py`: auxílio para descobrir o ID da conversa no Telegram.
- `teste_telegram.py`: teste de envio de mensagens.
- `requirements.txt` e `Dockerfile`: dependências e execução em contêiner.

## Configuração local

1. Instale Python e as dependências listadas em `requirements.txt`.
2. Instale o navegador utilizado pelo Playwright com `python -m playwright install chromium`.
3. Crie um arquivo `.env` na raiz do projeto com estas variáveis:

```dotenv
FEVER_URL=https://exemplo.com/pagina-do-evento
TELEGRAM_BOT_TOKEN=seu_token_do_bot
TELEGRAM_CHAT_ID=id_da_conversa
```

4. Teste o Telegram com `python teste_telegram.py`.
5. Execute uma verificação com `python monitor_fever.py`.

**Nunca publique seu `.env`, token do Telegram ou dados privados.** O `.gitignore` deve impedir o versionamento desses arquivos.

## Execução contínua

O script realiza **uma verificação por execução**. Para monitoramento recorrente, agende-o externamente (por exemplo, com cron). Se executar em Docker, preserve o arquivo `estado.txt` entre execuções para manter o histórico do último estado.

## Limitações

- O reconhecimento de disponibilidade depende dos textos e da estrutura da página, que podem mudar.
- Uma indicação de compra na página não garante ingressos disponíveis no momento da conclusão do pedido.
- Respeite os termos de uso do serviço e evite frequências excessivas de consultas.

## Uso

Projeto pessoal de automação e monitoramento. Não é afiliado à Fever.

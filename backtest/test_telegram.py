import asyncio
from telegram import Bot
from local__config import LOC_TLGRM_CHATID, LOC_TLGRM_TK

import requests

# Mensaje que deseas enviar
MESSAGE = "¡Hola! Este mensaje se envió con solicitudes HTTP."

# URL de la API de Telegram
url = f"https://api.telegram.org/bot{LOC_TLGRM_TK}/sendMessage"

# Datos del mensaje
payload = {
    'chat_id': LOC_TLGRM_CHATID,
    'text': MESSAGE
}

# Enviar el mensaje
response = requests.post(url, data=payload)

# Mostrar la respuesta
print(response.json())
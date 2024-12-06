import asyncio
from telegram import Bot


#TraderBot https://web.telegram.org/a/#6481383367
#TraderBot user @lbisaro_bot
#https://t.me/lbisaro_bot

LOC_TLGRM_CHATID = 1970865702

#lbisaro_bot
#LOC_TLGRM_TK = "6481383367:AAF0bItPpSUuLewpO0afp-D2P0O2R-Xar2I"
#LOC_TLGRM_CHATID = 1970865702

#trd_app_bot
LOC_TLGRM_TK = "7769731197:AAEJVd_OsI9SkaFSVh09OV6az0YY4MGNHRw"

"""

# Mensaje que quieres enviar
MESSAGE = "¡Hola, este es un mensaje enviado por mi bot de Telegram!"

async def send_message():
    bot = Bot(token=LOC_TLGRM_TK)
    await bot.send_message(chat_id=LOC_TLGRM_CHATID, text=MESSAGE)

if __name__ == "__main__":
    asyncio.run(send_message())
"""


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
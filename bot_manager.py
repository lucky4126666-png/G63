import telegram
from telegram.request import HTTPXRequest

bots = {}

def get_bot(token):
    if token not in bots:
        bots[token] = telegram.Bot(
            token=token,
            request=HTTPXRequest(connection_pool_size=10)
        )
    return bots[token]

async def send(token, chat_id, text):
    bot = get_bot(token)
    await bot.send_message(chat_id, text)

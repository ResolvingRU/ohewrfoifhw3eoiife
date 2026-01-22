import os
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from httpx import AsyncClient, Proxy

BOT_TOKEN = os.getenv("BOT_TOKEN", "8455072205:AAE9d7g3ZRxMSWgi3nv3XuoQqh7xiN71nGk")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://bottle-game-eorv.onrender.com")
PROXY_URL = os.getenv("PROXY_URL", None)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    keyboard = [
        [InlineKeyboardButton(
            "🍾 Играть в Бутылочку",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Добро пожаловать в игру *Бутылочка* 💋\n\n"
        "Жми на кнопку ниже чтобы начать играть!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


def main():
    """Запуск бота"""
    builder = Application.builder().token(BOT_TOKEN)

    if PROXY_URL:
        proxy = Proxy(url=PROXY_URL)
        http_client = AsyncClient(proxy=proxy, timeout=30.0)
        builder = builder.get_updates_http_client(http_client).http_client(http_client)

    app = builder.build()
    app.add_handler(CommandHandler("start", start))

    print("🤖 Бот запущен!")
    print("📡 Подключение к Telegram...")

    try:
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("\n💡 Включи VPN и попробуй снова")


if __name__ == "__main__":
    main()
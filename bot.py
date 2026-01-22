import os
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from httpx import AsyncClient, Proxy

# Токен бота получишь у @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "8455072205:AAE9d7g3ZRxMSWgi3nv3XuoQqh7xiN71nGk")

# URL твоего Mini App (после деплоя на Railway/Render)
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.railway.app")

# ПРОКСИ (если нужен) - раскомментируй и вставь свой
PROXY_URL = os.getenv("PROXY_URL", None)  # Например: "http://proxy.example.com:8080"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - показываем кнопку игры"""
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
        "Нажми на кнопку ниже чтобы начать играть!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


def main():
    """Запуск бота"""
    # Создаем builder
    builder = Application.builder().token(BOT_TOKEN)

    # Добавляем прокси если нужен
    if PROXY_URL:
        proxy = Proxy(url=PROXY_URL)
        http_client = AsyncClient(proxy=proxy, timeout=30.0)
        builder = builder.get_updates_http_client(http_client).http_client(http_client)

    app = builder.build()

    # Обработчики
    app.add_handler(CommandHandler("start", start))

    print("🤖 Бот запущен!")
    print("📡 Подключение к Telegram...")

    try:
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("\n💡 Возможные решения:")
        print("1. Включи VPN/прокси")
        print("2. Проверь интернет")
        print("3. Добавь прокси в .env файл")


if __name__ == "__main__":
    main()
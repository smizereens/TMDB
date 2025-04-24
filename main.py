import logging
import os
import asyncio # Импорт asyncio для gather
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler # Импорт CallbackQueryHandler

# Импорт обработчиков из bot_logic
import bot_logic

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Установка более высокого уровня логирования для httpx, чтобы избежать логирования всех GET и POST запросов
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def main() -> None:
    """Запускает бота."""
    # Загрузка переменных окружения из файла .env
    load_dotenv()
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TMDB_API_KEY = os.getenv('TMDB_API_KEY') # Загружаем ключ TMDB для проверки его наличия

    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения. Выход.")
        return
    if not TMDB_API_KEY:
        logger.error("TMDB_API_KEY не найден в переменных окружения. Проверьте файл .env, но продолжаем...")
        # Разрешаем продолжение, но вызовы API будут неудачными

    # Создание Application и передача токена вашего бота.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- Регистрация обработчиков ---
    # Основные команды
    application.add_handler(CommandHandler("start", bot_logic.start))
    application.add_handler(CommandHandler("help", bot_logic.help_command))
    application.add_handler(CommandHandler("search", bot_logic.search_command))
    application.add_handler(CommandHandler("popular", bot_logic.popular_command))
    application.add_handler(CommandHandler("toprated", bot_logic.toprated_command))
    application.add_handler(CommandHandler("upcoming", bot_logic.upcoming_command))

    # --- Обработчики диалогов ---
    application.add_handler(bot_logic.discover_conv_handler)
    application.add_handler(bot_logic.search_conv_handler) # Добавляем диалог поиска

    # --- Обработчики Callback Query ---
    application.add_handler(bot_logic.pagination_handler) # Обрабатывает кнопки next/prev

    # --- Обработчики сообщений для кнопок ---
    # Их следует добавлять после CommandHandlers и ConversationHandlers,
    # чтобы команды вроде /start имели приоритет над текстом кнопок
    application.add_handler(bot_logic.popular_button_handler)
    application.add_handler(bot_logic.toprated_button_handler)
    application.add_handler(bot_logic.upcoming_button_handler)
    application.add_handler(bot_logic.help_button_handler)

    # Примечание: команда cancel зарегистрирована в fallbacks ConversationHandler

    logger.info("Обработчики бота зарегистрированы.")

    # Запуск бота до нажатия Ctrl-C
    logger.info("Запуск опроса бота...")
    # Предварительная загрузка кэшей перед запуском опроса (опционально, но хорошая практика)
    # asyncio.run(bot_logic.ensure_api_config_cached()) # Уже вызывается в обработчике start
    # asyncio.run(bot_logic.ensure_genres_cached()) # Уже вызывается в обработчике start
    application.run_polling()
    logger.info("Бот остановлен.")

if __name__ == "__main__":
    # Используйте asyncio.run(), если ваши функции верхнего уровня асинхронны
    # Для run_polling, она синхронна на верхнем уровне.
    main()

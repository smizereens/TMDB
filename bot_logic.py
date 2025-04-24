import logging
import html  # Import the html module for escaping
import asyncio # Import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.error import BadRequest, RetryAfter # Import errors
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
)
import tmdb_api # Import our API module

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Глобальные переменные и константы ---
# Кэш для жанров и конфигурации API для избежания частых запросов
GENRES_CACHE = {}
API_CONFIG_CACHE = {}
# Состояния диалога для команды /discover
(ASK_GENRE, ASK_YEAR, ASK_RATING, SHOW_DISCOVERY_RESULTS) = range(4) # Для /discover
ASK_SEARCH_QUERY = range(4, 5) # Для поиска по кнопке

# Ключи пользовательских данных
DISCOVERY_CRITERIA = 'discovery_criteria'
PAGINATED_RESULTS = 'paginated_results'
CURRENT_INDEX = 'current_index'

# Тексты кнопок клавиатуры
BTN_SEARCH = "🔍 Поиск"
BTN_DISCOVER = "💡 Подобрать" # Изменено с текста команды /discover
BTN_POPULAR = "⭐ Популярные"
BTN_TOP_RATED = "🏆 Топ Рейтинг"
BTN_UPCOMING = "📅 Скоро"
BTN_HELP = "❓ Помощь"

MAIN_KEYBOARD = [
    [BTN_SEARCH, BTN_DISCOVER],
    [BTN_POPULAR, BTN_TOP_RATED, BTN_UPCOMING],
    [BTN_HELP]
]
MAIN_REPLY_MARKUP = ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True)


# --- Вспомогательные функции ---

async def ensure_api_config_cached():
    """Гарантирует, что конфигурация API получена и закэширована."""
    global API_CONFIG_CACHE
    if not API_CONFIG_CACHE or 'images' not in API_CONFIG_CACHE:
        logger.info("Конфигурация API не кэширована или невалидна. Запрашиваю...")
        API_CONFIG_CACHE = tmdb_api.get_api_config()
        if not API_CONFIG_CACHE or 'images' not in API_CONFIG_CACHE:
            logger.error("Не удалось получить или кэшировать валидную конфигурацию API.")
            API_CONFIG_CACHE = {} # Сброс кэша при ошибке
            return False
        logger.info("Конфигурация API успешно кэширована.")
    return True

async def ensure_genres_cached():
    """Гарантирует, что жанры фильмов получены и закэшированы."""
    global GENRES_CACHE
    if not GENRES_CACHE:
        logger.info("Жанры не кэшированы. Запрашиваю...")
        genres_data = tmdb_api.get_genres()
        if genres_data and 'genres' in genres_data:
            GENRES_CACHE = {genre['name'].lower(): genre['id'] for genre in genres_data['genres']}
            logger.info("Жанры успешно кэшированы.")
        else:
            logger.error("Не удалось получить или кэшировать жанры.")
            GENRES_CACHE = {} # Сброс кэша при ошибке
            return False
    return True

def format_movie_details(movie_data):
    """Форматирует данные фильма в читаемую строку для Telegram с использованием HTML."""
    if not movie_data:
        return "Не удалось получить информацию о фильме.", None

    # Основная информация - Экранируем HTML символы из полей API
    title = html.escape(movie_data.get('title', 'N/A'))
    original_title = html.escape(movie_data.get('original_title', ''))
    overview = html.escape(movie_data.get('overview', 'Описание недоступно.'))
    release_date = movie_data.get('release_date', 'N/A') # Дата безопасна
    rating = movie_data.get('vote_average', 0)
    vote_count = movie_data.get('vote_count', 0)
    # Экранируем названия жанров по отдельности
    genres_list = [html.escape(g['name']) for g in movie_data.get('genres', [])]
    genres = ', '.join(genres_list)
    runtime = movie_data.get('runtime', 0) # в минутах

    # Составляем сообщение с использованием HTML тегов
    message = f"🎬 <b>{title}</b>"
    # Проверяем оригинальное название *перед* экранированием для сравнения
    if movie_data.get('title', '').lower() != movie_data.get('original_title', '').lower() and original_title:
        message += f" ({original_title})" # Уже экранировано
    message += f"\n\n🗓️ Дата выхода: {release_date}"
    if genres:
        message += f"\n🎭 Жанры: {genres}" # Уже экранировано
    if runtime:
        message += f"\n⏱️ Продолжительность: {runtime} мин."
    message += f"\n⭐ Рейтинг: {rating:.1f}/10 ({vote_count} голосов)"
    message += f"\n\n📝 Описание:\n{overview}" # Уже экранировано

    # Добавляем URL постера, если доступна конфигурация
    poster_url = None
    if API_CONFIG_CACHE and 'images' in API_CONFIG_CACHE and movie_data.get('poster_path'):
        base_url = API_CONFIG_CACHE['images'].get('secure_base_url', '')
        # Выбираем подходящий размер постера (например, w500)
        poster_size = 'w500' # По умолчанию w500
        poster_sizes = API_CONFIG_CACHE['images'].get('poster_sizes', [])
        if 'w500' in poster_sizes:
             poster_size = 'w500'
        elif len(poster_sizes) > 1:
             # Пытаемся взять предпоследний размер, если w500 недоступен
             poster_size = poster_sizes[-2] if len(poster_sizes) >= 2 else poster_sizes[-1]
        elif poster_sizes:
             poster_size = poster_sizes[-1] # Резервный вариант - самый большой доступный
        else:
             poster_size = 'original' # Абсолютный резервный вариант

        poster_path = movie_data['poster_path']
        if base_url and poster_path:
            poster_url = f"{base_url}{poster_size}{poster_path}"
            # logger.info(f"Сформирован URL постера: {poster_url}") # Уменьшаем шум в логах
        else:
            logger.warning("Не удалось сформировать URL постера (отсутствует base_url или poster_path).")

    return message, poster_url # Возвращаем сообщение и опциональный URL постера


async def display_movie_result(update: Update, context: ContextTypes.DEFAULT_TYPE, index: int):
    """Отображает один результат фильма с кнопками пагинации."""
    results = context.user_data.get(PAGINATED_RESULTS, [])
    if not results or index < 0 or index >= len(results):
        logger.warning(f"Неверный индекс ({index}) или нет результатов для пагинации.")
        reply_target = update.callback_query.message if update.callback_query else update.message
        if reply_target:
            await reply_target.reply_text("Ошибка пагинации или нет результатов.")
        return

    movie = results[index]
    message_text, poster_url = format_movie_details(movie)
    context.user_data[CURRENT_INDEX] = index

    # --- Создание клавиатуры пагинации ---
    keyboard = []
    row = []
    if index > 0:
        row.append(InlineKeyboardButton("⬅️ Пред.", callback_data=f"prev_movie_{index - 1}"))
    if index < len(results) - 1:
        row.append(InlineKeyboardButton("След. ➡️", callback_data=f"next_movie_{index + 1}"))
    if row:
        keyboard.append(row)
    inline_reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    # Определяем правильную разметку ответа (inline для редактирования, основную для новых сообщений)
    final_reply_markup = inline_reply_markup if update.callback_query else (inline_reply_markup if results else MAIN_REPLY_MARKUP)


    # --- Отправка или редактирование сообщения ---
    reply_target = update.callback_query.message if update.callback_query else update.message
    if not reply_target:
         logger.error("Не удалось найти объект сообщения для ответа или редактирования.")
         return

    # --- Логика обработки нажатий кнопок (Callbacks) ---
    if update.callback_query:
        current_message = update.callback_query.message
        has_current_photo = bool(current_message.photo)
        has_new_photo = bool(poster_url)

        try:
            # Случай 1: Типы совпадают (фото->фото или текст->текст) - Редактируем
            if has_current_photo == has_new_photo:
                if has_new_photo: # Фото -> Фото
                     logger.info(f"Редактирую сообщение {current_message.message_id} с фото для фильма {movie.get('id')}")
                     await update.callback_query.edit_message_media(
                        media=InputMediaPhoto(media=poster_url, caption=message_text, parse_mode=ParseMode.HTML),
                        reply_markup=inline_reply_markup # Используем inline клавиатуру для редактирования
                    )
                else: # Текст -> Текст
                    logger.info(f"Редактирую сообщение {current_message.message_id} с текстом для фильма {movie.get('id')}")
                    await update.callback_query.edit_message_text(
                        text=message_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=inline_reply_markup, # Используем inline клавиатуру для редактирования
                        disable_web_page_preview=True
                    )
            # Случай 2: Типы не совпадают (фото->текст или текст->фото) - Удаляем и отправляем заново
            else:
                logger.info(f"Несовпадение типов сообщения при пагинации (фото: {has_current_photo} -> {has_new_photo}). Удаляю {current_message.message_id} и отправляю заново.")
                await current_message.delete()
                chat_id = current_message.chat_id
                if has_new_photo:
                    await context.bot.send_photo(chat_id=chat_id, photo=poster_url, caption=message_text, parse_mode=ParseMode.HTML, reply_markup=inline_reply_markup) # Используем inline клавиатуру
                else:
                    await context.bot.send_message(chat_id=chat_id, text=message_text, parse_mode=ParseMode.HTML, reply_markup=inline_reply_markup, disable_web_page_preview=True) # Используем inline клавиатуру

        except BadRequest as e:
            # Обрабатываем ошибку "message is not modified" без вывода в лог
            if "message is not modified" in str(e).lower():
                logger.info("Сообщение не изменено, игнорирую ошибку.")
                try: await update.callback_query.answer() # Просто подтверждаем нажатие кнопки
                except Exception: pass
            else:
                logger.error(f"BadRequest во время редактирования/переотправки пагинации для фильма {movie.get('id')}: {e}")
                try: await update.callback_query.answer("Ошибка при обновлении сообщения.", show_alert=True)
                except Exception: pass # Игнорируем, если ответ на callback не удался
        except Exception as e:
            # Обрабатываем другие неожиданные ошибки
            logger.error(f"Неожиданная ошибка во время редактирования/переотправки пагинации для фильма {movie.get('id')}: {e}")
            try: await update.callback_query.answer("Произошла ошибка.", show_alert=True)
            except Exception: pass # Игнорируем, если ответ на callback не удался

    # --- Логика обработки начальной команды (Отправка нового сообщения) ---
    else:
        try:
            if poster_url:
                logger.info(f"Отправляю начальное сообщение с фото для фильма {movie.get('id')}")
                await reply_target.reply_photo(photo=poster_url, caption=message_text, parse_mode=ParseMode.HTML, reply_markup=final_reply_markup)
            else:
                logger.info(f"Отправляю начальное сообщение с текстом для фильма {movie.get('id')}")
                await reply_target.reply_text(text=message_text, parse_mode=ParseMode.HTML, reply_markup=final_reply_markup, disable_web_page_preview=True)
        except RetryAfter as e:
             logger.error(f"Превышен лимит запросов при отправке начального сообщения для фильма {movie.get('id')}: {e}. Повтор через {e.retry_after}с.")
             # Опционально уведомляем пользователя о флуд-контроле
             await reply_target.reply_text(f"Слишком много запросов. Попробуйте через {e.retry_after} секунд.", reply_markup=MAIN_REPLY_MARKUP)
        except Exception as e:
            # Упрощенный fallback при ошибке отправки начального сообщения
            logger.error(f"Ошибка отправки начального сообщения для фильма {movie.get('id')}: {e}. Отправляю обычный текст.")
            try:
                # Переформатируем без HTML для fallback'а
                plain_title = html.unescape(html.escape(movie.get('title', 'N/A'))) # Получаем сырое и раскодируем
                plain_original_title = html.unescape(html.escape(movie.get('original_title', '')))
                plain_overview = html.unescape(html.escape(movie.get('overview', 'Описание недоступно.')))
                plain_genres_list = [html.unescape(html.escape(g['name'])) for g in movie.get('genres', [])]
                plain_genres = ', '.join(plain_genres_list)
                plain_runtime = movie.get('runtime', 0)
                plain_rating = movie.get('vote_average', 0)
                plain_vote_count = movie.get('vote_count', 0)
                plain_release_date = movie.get('release_date', 'N/A')

                plain_text = f"🎬 {plain_title}"
                if movie.get('title', '').lower() != movie.get('original_title', '').lower() and plain_original_title:
                     plain_text += f" ({plain_original_title})"
                plain_text += f"\n\n🗓️ Дата выхода: {plain_release_date}"
                if plain_genres:
                     plain_text += f"\n🎭 Жанры: {plain_genres}"
                if plain_runtime:
                     plain_text += f"\n⏱️ Продолжительность: {plain_runtime} мин."
                plain_text += f"\n⭐ Рейтинг: {plain_rating:.1f}/10 ({plain_vote_count} голосов)"
                plain_text += f"\n\n📝 Описание:\n{plain_overview}"
                await reply_target.reply_text(plain_text, reply_markup=final_reply_markup, disable_web_page_preview=True)
            except Exception as e2:
                logger.error(f"Не удалось отправить даже обычный текст для фильма {movie.get('id')}: {e2}")


async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия кнопок 'next' и 'previous' для результатов фильмов."""
    query = update.callback_query
    await query.answer() # Подтверждаем нажатие кнопки

    data = query.data
    logger.info(f"Получен callback пагинации: {data}")

    try:
        action, new_index_str = data.split("_", 2)[1:] # например, "next", "movie", "5" -> "movie", "5"
        new_index = int(new_index_str)
    except (ValueError, IndexError) as e:
        logger.error(f"Ошибка парсинга данных callback'а пагинации '{data}': {e}")
        # Пытаемся ответить на callback, если возможно
        try: await query.answer("Ошибка пагинации.", show_alert=True)
        except Exception: pass
        return

    await display_movie_result(update, context, new_index)


# --- Обработчики команд ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение и основную клавиатуру."""
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}!\n\n"
        f"Я помогу тебе найти фильмы. Используй кнопки ниже или команду /help.",
        reply_markup=MAIN_REPLY_MARKUP
    )
    # Предварительно кэшируем конфигурацию и жанры при старте
    await asyncio.gather(
        ensure_api_config_cached(),
        ensure_genres_cached()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение со всеми доступными командами при вызове /help."""
    # Используем HTML форматирование для текста помощи
    help_text = """
<b>Доступные команды и кнопки:</b>
/start - Показать приветствие и кнопки
/help или кнопка '❓ Помощь' - Показать это сообщение
Кнопка '🔍 Поиск' или /search <code><название></code> - Поиск по названию
Кнопка '💡 Подобрать' или /discover - Пошаговый подбор по критериям
Кнопка '⭐ Популярные' или /popular - Показать популярные фильмы
Кнопка '🏆 Топ Рейтинг' или /toprated - Показать фильмы с высоким рейтингом
Кнопка '📅 Скоро' или /upcoming - Показать скоро выходящие фильмы
/cancel - Отменить текущую операцию (поиск или подбор)
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML, reply_markup=MAIN_REPLY_MARKUP)

# --- Логика кнопок/команд ---

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    """Основная логика для выполнения поиска и отображения результатов."""
    logger.info(f"Обработка поиска по запросу: {query}")
    api_results = tmdb_api.search_movies(query)

    # Не фильтруем результаты поиска по количеству голосов изначально,
    # чтобы находить точные совпадения названий, например "Начало"
    if api_results and api_results.get('results'):
        context.user_data[PAGINATED_RESULTS] = api_results['results'] # Используем сырые результаты
        await display_movie_result(update, context, 0) # Отображаем первый результат
    elif api_results is None:
         # Убеждаемся, что основная клавиатура показана при ошибке API после поиска по кнопке
         await update.message.reply_text("Произошла ошибка при запросе к API. Попробуйте позже.", reply_markup=MAIN_REPLY_MARKUP)
    else:
         # Убеждаемся, что основная клавиатура показана при отсутствии результатов после поиска по кнопке
        await update.message.reply_text("По вашему запросу ничего не найдено.", reply_markup=MAIN_REPLY_MARKUP)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /search напрямую."""
    query = " ".join(context.args)
    if not query:
        example_command = html.escape("/search Начало")
        await update.message.reply_text(f"Пожалуйста, укажите название фильма после команды /search.\nПример: <code>{example_command}</code>", parse_mode=ParseMode.HTML, reply_markup=MAIN_REPLY_MARKUP)
        return
    await handle_search(update, context, query)


async def popular_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /popular или нажатие кнопки."""
    logger.info("Обработка запроса Популярные.")
    api_results = tmdb_api.get_popular_movies()
    # Сначала отправляем заголовок, затем результаты
    await update.message.reply_text("<b>Популярные фильмы (голосов > 1000):</b>", parse_mode=ParseMode.HTML, reply_markup=MAIN_REPLY_MARKUP)

    if api_results and api_results.get('results'):
         # Фильтруем результаты по количеству голосов >= 1000 (т.к. эндпоинт API это не поддерживает)
        filtered_results = [m for m in api_results['results'] if m.get('vote_count', 0) >= 1000]
        if filtered_results:
            context.user_data[PAGINATED_RESULTS] = filtered_results
            await display_movie_result(update, context, 0) # Отображаем первый результат
        else:
            await update.message.reply_text("Не найдено популярных фильмов с достаточным количеством голосов (>1000).", reply_markup=MAIN_REPLY_MARKUP)
    elif api_results is None:
         await update.message.reply_text("Произошла ошибка при запросе к API. Попробуйте позже.", reply_markup=MAIN_REPLY_MARKUP)
    else:
        await update.message.reply_text("Не найдено популярных фильмов.", reply_markup=MAIN_REPLY_MARKUP)


async def toprated_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /toprated или нажатие кнопки."""
    logger.info("Обработка запроса Топ Рейтинг.")
    api_results = tmdb_api.get_top_rated_movies() # Уже отфильтровано API
    # Сначала отправляем заголовок, затем результаты
    await update.message.reply_text("<b>Фильмы с высоким рейтингом (голосов > 1000):</b>", parse_mode=ParseMode.HTML, reply_markup=MAIN_REPLY_MARKUP)

    if api_results and api_results.get('results'):
        context.user_data[PAGINATED_RESULTS] = api_results['results']
        await display_movie_result(update, context, 0) # Отображаем первый результат
    elif api_results is None:
         await update.message.reply_text("Произошла ошибка при запросе к API. Попробуйте позже.", reply_markup=MAIN_REPLY_MARKUP)
    else:
        await update.message.reply_text("Не найдено фильмов с высоким рейтингом и достаточным количеством голосов.", reply_markup=MAIN_REPLY_MARKUP)


async def upcoming_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /upcoming или нажатие кнопки."""
    logger.info("Обработка запроса Скоро.")
    api_results = tmdb_api.get_upcoming_movies()
    # Сначала отправляем заголовок, затем результаты
    await update.message.reply_text("<b>Скоро в кино:</b>", parse_mode=ParseMode.HTML, reply_markup=MAIN_REPLY_MARKUP)

    if api_results and api_results.get('results'):
        # Скоро выходящие фильмы часто имеют мало голосов, поэтому не фильтруем их
        context.user_data[PAGINATED_RESULTS] = api_results['results']
        await display_movie_result(update, context, 0) # Отображаем первый результат
    elif api_results is None:
         await update.message.reply_text("Произошла ошибка при запросе к API. Попробуйте позже.", reply_markup=MAIN_REPLY_MARKUP)
    else:
        await update.message.reply_text("Не найдено скоро выходящих фильмов.", reply_markup=MAIN_REPLY_MARKUP)


# --- Обработчики диалогов (/discover) ---

# --- Диалог поиска по кнопке ---

async def search_button_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает нажатие кнопки поиска, запрашивает запрос."""
    logger.info("Обработка нажатия кнопки Поиск.")
    await update.message.reply_text("Введите название фильма для поиска:", reply_markup=ReplyKeyboardRemove())
    return ASK_SEARCH_QUERY

async def search_query_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод названия фильма пользователем после нажатия кнопки поиска."""
    query = update.message.text
    if not query:
        await update.message.reply_text("Пожалуйста, введите название.", reply_markup=MAIN_REPLY_MARKUP)
        return ConversationHandler.END # Или спросить снова? Завершаем для простоты.

    # Вызываем общую логику поиска
    await handle_search(update, context, query)
    # Отправляем сообщение для возврата основной клавиатуры
    await update.message.reply_text("Выберите следующее действие:", reply_markup=MAIN_REPLY_MARKUP)
    return ConversationHandler.END


# --- Диалог подбора (/discover или кнопка) ---

async def discover_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог подбора (из команды или кнопки)."""
    logger.info("Обработка запроса Подобрать, начало диалога.")
    await ensure_genres_cached()
    if not GENRES_CACHE:
         await update.message.reply_text("Не удалось загрузить список жанров. Попробуйте позже.", reply_markup=MAIN_REPLY_MARKUP)
         return ConversationHandler.END

    context.user_data[DISCOVERY_CRITERIA] = {} # Инициализируем словарь критериев

    # Создаем inline клавиатуру с жанрами
    keyboard = []
    row = []
    genres_sorted = sorted(GENRES_CACHE.keys())
    for i, genre_name in enumerate(genres_sorted):
        row.append(InlineKeyboardButton(genre_name.capitalize(), callback_data=f"genre_{GENRES_CACHE[genre_name]}"))
        if len(row) == 3 or i == len(genres_sorted) - 1: # 3 кнопки в ряду
            keyboard.append(row)
            row = []
    keyboard.append([InlineKeyboardButton("Пропустить", callback_data="skip_genre")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Давайте подберем фильм! Выберите жанр:", reply_markup=reply_markup)
    return ASK_GENRE

async def ask_genre_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор жанра из inline клавиатуры."""
    query = update.callback_query
    await query.answer()
    callback_data = query.data

    if callback_data == "skip_genre":
        logger.info("Пользователь пропустил выбор жанра.")
        await query.edit_message_text(text="Жанр пропущен.")
    elif callback_data.startswith("genre_"):
        genre_id = callback_data.split("_")[1]
        context.user_data[DISCOVERY_CRITERIA]['with_genres'] = genre_id
        # Находим имя жанра для подтверждающего сообщения
        genre_name = "Выбранный жанр"
        for name, gid in GENRES_CACHE.items():
            if str(gid) == genre_id:
                genre_name = name.capitalize()
                break
        logger.info(f"Пользователь выбрал жанр ID: {genre_id} ({genre_name})")
        await query.edit_message_text(text=f"Выбран жанр: {genre_name}")

    # Спрашиваем год
    await query.message.reply_text("Теперь введите год выпуска (например, 2023) или напишите 'пропустить':", reply_markup=ReplyKeyboardRemove()) # Убираем основную клавиатуру во время диалога
    return ASK_YEAR


async def ask_year_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод года пользователем."""
    user_input = update.message.text.lower()
    criteria = context.user_data[DISCOVERY_CRITERIA]

    if user_input == 'пропустить':
        logger.info("Пользователь пропустил выбор года.")
        await update.message.reply_text("Год пропущен.")
    elif user_input.isdigit() and len(user_input) == 4:
        year = int(user_input)
        criteria['primary_release_year'] = year
        logger.info(f"Пользователь ввел год: {year}")
        await update.message.reply_text(f"Выбран год: {year}")
    else:
        # Отступ этой строки
        await update.message.reply_text("Неверный формат года. Пожалуйста, введите 4 цифры (например, 2023) или 'пропустить'.", reply_markup=ReplyKeyboardRemove())
        return ASK_YEAR # Остаемся в том же состоянии

    # Спрашиваем минимальный рейтинг
    keyboard = [
        [
            InlineKeyboardButton("Любой", callback_data="rating_any"),
            InlineKeyboardButton("6+", callback_data="rating_6"),
            InlineKeyboardButton("7+", callback_data="rating_7"),
            InlineKeyboardButton("8+", callback_data="rating_8"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите минимальный рейтинг:", reply_markup=reply_markup)
    return ASK_RATING

async def ask_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор минимального рейтинга."""
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    criteria = context.user_data[DISCOVERY_CRITERIA]

    rating_text = "Любой"
    if callback_data == "rating_6":
        criteria['vote_average.gte'] = 6
        rating_text = "6+"
    elif callback_data == "rating_7":
        criteria['vote_average.gte'] = 7
        rating_text = "7+"
    elif callback_data == "rating_8":
        criteria['vote_average.gte'] = 8
        rating_text = "8+"

    logger.info(f"Пользователь выбрал минимальный рейтинг: {rating_text}")
    await query.edit_message_text(text=f"Выбран минимальный рейтинг: {rating_text}")

    # --- Выполняем подбор ---
    logger.info(f"Выполняю подбор по критериям: {criteria}")
    # Сначала отправляем заголовок, затем результаты
    await query.message.reply_text("Ищу фильмы по вашим критериям (голосов > 1000)...", reply_markup=MAIN_REPLY_MARKUP) # Показываем основную клавиатуру снова
    api_results = tmdb_api.discover_movies(criteria) # Уже отфильтровано API

    if api_results and api_results.get('results'):
        context.user_data[PAGINATED_RESULTS] = api_results['results']
        await display_movie_result(update, context, 0) # Отображаем первый результат
    elif api_results is None:
         await query.message.reply_text("Произошла ошибка при запросе к API. Попробуйте позже.", reply_markup=MAIN_REPLY_MARKUP)
    else:
        await query.message.reply_text("Не найдено фильмов по вашим критериям.", reply_markup=MAIN_REPLY_MARKUP)


    # Очищаем пользовательские данные и завершаем диалог
    if DISCOVERY_CRITERIA in context.user_data:
        del context.user_data[DISCOVERY_CRITERIA]
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет и завершает диалог."""
    user = update.effective_user
    logger.info(f"Пользователь {user.first_name} отменил диалог.")
    # Очищаем данные для обоих типов диалогов
    if DISCOVERY_CRITERIA in context.user_data:
        del context.user_data[DISCOVERY_CRITERIA]
    if PAGINATED_RESULTS in context.user_data: # Также очищаем результаты при отмене
        del context.user_data[PAGINATED_RESULTS]
    if CURRENT_INDEX in context.user_data:
        del context.user_data[CURRENT_INDEX]

    await update.message.reply_text(
        "Операция отменена.", reply_markup=MAIN_REPLY_MARKUP
    )
    return ConversationHandler.END

# --- Настройки обработчиков диалогов ---

# Диалог подбора
discover_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("discover", discover_start), MessageHandler(filters.Regex(f"^{BTN_DISCOVER}$"), discover_start)],
    states={
        ASK_GENRE: [CallbackQueryHandler(ask_genre_callback, pattern="^(genre_|skip_genre)")],
        ASK_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_year_input)],
        ASK_RATING: [CallbackQueryHandler(ask_rating_callback, pattern="^rating_")],
        # Состояние SHOW_DISCOVERY_RESULTS не нужно, т.к. обработка в ask_rating_callback
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    # Опционально: добавить сохранение состояния диалога при необходимости
)

# Диалог поиска по кнопке
search_conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex(f"^{BTN_SEARCH}$"), search_button_start)],
    states={
        ASK_SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_query_input)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)


# --- Обработчик пагинации ---
pagination_handler = CallbackQueryHandler(handle_pagination, pattern="^(prev_movie_|next_movie_)")

# --- Обработчики сообщений для кнопок ---
# Они напрямую связывают текст кнопки с функциями команд
popular_button_handler = MessageHandler(filters.Regex(f"^{BTN_POPULAR}$"), popular_command)
toprated_button_handler = MessageHandler(filters.Regex(f"^{BTN_TOP_RATED}$"), toprated_command)
upcoming_button_handler = MessageHandler(filters.Regex(f"^{BTN_UPCOMING}$"), upcoming_command)
help_button_handler = MessageHandler(filters.Regex(f"^{BTN_HELP}$"), help_command)

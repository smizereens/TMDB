# TMDB Telegram Bot

Этот Telegram-бот позволяет искать и подбирать фильмы с использованием API The Movie Database (TMDB).

## Функции

*   Поиск фильмов по названию (`/search <название>` или кнопка "🔍 Поиск").
*   Подбор фильмов по критериям (жанр, год, рейтинг) (`/discover` или кнопка "💡 Подобрать").
*   Просмотр популярных фильмов (`/popular` или кнопка "⭐ Популярные").
*   Просмотр фильмов с высоким рейтингом (`/toprated` или кнопка "🏆 Топ Рейтинг").
*   Просмотр скоро выходящих фильмов (`/upcoming` или кнопка "📅 Скоро").
*   Пагинация результатов с кнопками "Пред." и "След.".
*   Отображение постеров фильмов (если доступны).
*   Интерфейс с кнопками для основных действий.

## Установка и запуск

1.  **Клонируйте репозиторий (если применимо):**
    ```bash
    git clone https://github.com/smizereens/TMDB.git
    ```

2.  **Создайте и активируйте виртуальное окружение:**
    ```bash
    python -m venv venv

    # Windows (Command Prompt)
    python -m venv venv
    venv\Scripts\activate

    # Windows (PowerShell)
    python -m venv venv
    .\venv\Scripts\Activate.ps1

    # macOS / Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Установите зависимости:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Настройте API ключи:**
    *   Создайте файл с именем `.env` в корневой папке проекта.
    *   Добавьте в него ваши ключи API:
        ```dotenv
        TMDB_API_KEY=ВАШ_TMDB_API_КЛЮЧ_ЗДЕСЬ
        TELEGRAM_BOT_TOKEN=ВАШ_TELEGRAM_BOT_ТОКЕН_ЗДЕСЬ
        ```
    *   Получите TMDB API ключ здесь: [https://www.themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
    *   Получите Telegram Bot токен от BotFather в Telegram.

5.  **Запустите бота:**
    ```bash
    python main.py
    ```

6.  **Взаимодействуйте с ботом в Telegram.**

## Файлы проекта

*   `main.py`: Основной скрипт для запуска бота.
*   `bot_logic.py`: Содержит логику обработки команд, диалогов и пагинации.
*   `tmdb_api.py`: Модуль для взаимодействия с TMDB API.
*   `requirements.txt`: Список необходимых Python библиотек.
*   `.env`: Файл для хранения секретных ключей API (не должен попадать в Git).

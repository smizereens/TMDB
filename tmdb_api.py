import os
import requests
from dotenv import load_dotenv
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения из файла .env
load_dotenv()

# Получение API ключа и определение базового URL
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
BASE_URL = "https://api.themoviedb.org/3"

if not TMDB_API_KEY:
    logger.error("TMDB_API_KEY не найден в переменных окружения. Проверьте ваш файл .env.")
    # Здесь можно выбросить исключение или завершить работу в зависимости от желаемого поведения
    # raise ValueError("TMDB_API_KEY не найден.")

# --- Вспомогательная функция ---
def _make_request(endpoint, params=None):
    """Вспомогательная функция для выполнения запросов к TMDB API."""
    if not TMDB_API_KEY:
        logger.error("Невозможно выполнить API запрос без TMDB_API_KEY.")
        return None

    if params is None:
        params = {}

    # Установка языка по умолчанию на русский, с резервным en-US
    params.setdefault('language', 'ru-RU')

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TMDB_API_KEY}"
    }

    url = f"{BASE_URL}{endpoint}"
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Выбросить исключение для плохих статус-кодов (4xx или 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка API запроса для эндпоинта {endpoint}: {e}")
        logger.error(f"URL: {response.url if 'response' in locals() else url}")
        logger.error(f"Статус код: {response.status_code if 'response' in locals() else 'N/A'}")
        logger.error(f"Текст ответа: {response.text if 'response' in locals() else 'N/A'}")
        return None
    except Exception as e:
        logger.error(f"Произошла непредвиденная ошибка во время API запроса к {endpoint}: {e}")
        return None

# --- Функции API ---

def get_api_config():
    """Запрашивает детали конфигурации API, такие как базовые URL изображений."""
    logger.info("Запрос конфигурации API.")
    return _make_request("/configuration")

def get_genres():
    """Запрашивает список официальных жанров фильмов."""
    logger.info("Запрос списка жанров фильмов.")
    return _make_request("/genre/movie/list")

def search_movies(query, page=1, include_adult=False):
    """Ищет фильмы по названию."""
    logger.info(f"Поиск фильмов по запросу: '{query}', страница: {page}")
    params = {
        'query': query,
        'page': page,
        'include_adult': include_adult
    }
    return _make_request("/search/movie", params=params)

def discover_movies(criteria, page=1):
    """
    Подбирает фильмы по различным критериям.
    'criteria' должен быть словарем параметров, таких как:
    'with_genres', 'primary_release_year', 'vote_average.gte', и т.д.
    """
    logger.info(f"Подбор фильмов по критериям: {criteria}, страница: {page}")
    params = criteria.copy() # Избегаем изменения оригинального словаря
    params['page'] = page
    # Добавляем другие параметры по умолчанию при необходимости, например, sort_by
    params.setdefault('sort_by', 'popularity.desc')
    # Добавляем фильтр по количеству голосов
    params['vote_count.gte'] = 1000
    return _make_request("/discover/movie", params=params)

def get_movie_details(movie_id, append_to_response=None):
    """Получает детальную информацию по конкретному фильму."""
    logger.info(f"Запрос деталей для фильма ID: {movie_id}")
    endpoint = f"/movie/{movie_id}"
    params = {}
    if append_to_response:
        params['append_to_response'] = append_to_response
    return _make_request(endpoint, params=params)

def get_popular_movies(page=1, region=None):
    """Получает список популярных фильмов."""
    logger.info(f"Запрос популярных фильмов, страница: {page}")
    params = {'page': page}
    if region:
        params['region'] = region
    # Фильтр по количеству голосов - Примечание: эндпоинт /movie/popular не поддерживает vote_count.gte напрямую
    # Возможно, потребуется фильтровать результаты позже или использовать /discover с sort_by=popularity.desc
    # Пока оставим так и будем фильтровать позже при необходимости.
    # params['vote_count.gte'] = 1000 # Это не сработает на /movie/popular
    return _make_request("/movie/popular", params=params)

def get_top_rated_movies(page=1, region=None):
    """Получает список фильмов с высоким рейтингом."""
    logger.info(f"Запрос фильмов с высоким рейтингом, страница: {page}")
    params = {'page': page}
    if region:
        params['region'] = region
    # Добавляем фильтр по количеству голосов
    params['vote_count.gte'] = 1000
    return _make_request("/movie/top_rated", params=params)

def get_upcoming_movies(page=1, region=None):
    """Получает список скоро выходящих фильмов."""
    logger.info(f"Запрос скоро выходящих фильмов, страница: {page}")
    params = {'page': page}
    if region:
        params['region'] = region
    return _make_request("/movie/upcoming", params=params)

# Пример использования (для целей тестирования)
if __name__ == '__main__':
    config = get_api_config()
    if config and 'images' in config:
        print("Конфигурация API успешно получена.")
        # print(f"Базовый URL изображений: {config['images']['secure_base_url']}")
    else:
        print("Не удалось получить конфигурацию API.")

    genres = get_genres()
    if genres and 'genres' in genres:
        print("\nЖанры успешно получены.")
        # print(genres['genres'])
    else:
        print("\nНе удалось получить жанры.")

    # Пример поиска
    # search_results = search_movies("Начало")
    # if search_results:
    #     print("\nРезультаты поиска для 'Начало':")
    #     # print(search_results)

    # Пример подбора
    # discover_criteria = {'with_genres': '28', 'primary_release_year': 2022} # Боевики 2022 года
    # discover_results = discover_movies(discover_criteria)
    # if discover_results:
    #     print("\nРезультаты подбора для боевиков 2022 года:")
        # print(discover_results)

    # Пример популярных
    # popular_movies = get_popular_movies()
    # if popular_movies:
    #     print("\nПопулярные фильмы:")
        # print(popular_movies)

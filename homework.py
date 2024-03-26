import logging
import os
import requests
import telegram
import time

from dotenv import load_dotenv

from exceptions import ResponseExeption, CheckTokenExeption

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверка наличия токенов."""
    tokens = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    for token in tokens:
        if token is None:
            logger.critical(
                f'Отсутствует переменная окружения {token}'
            )
            raise CheckTokenExeption(
                f'Отсутствует переменная окружения {token}'
            )


def send_message(bot, message):
    """Отправка сообщений."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Отправлено сообщение: {message}')
    except Exception as error:
        logger.error(f'Ошибка отправки сообщения: {error}')


def get_api_answer(timestamp):
    """Получение ответа API."""
    payload = {'from_date': timestamp}
    try:
        request = requests.get(ENDPOINT,
                               headers=HEADERS,
                               params=payload)
    except requests.RequestException as error:
        logger.error(f'Ошибка ответа API: {error}')
    if request.status_code != 200:
        logger.error(f'Ошибка ответа API: {request.status_code}')
        raise ResponseExeption(f'Ошибка ответа API: {request.status_code}')
    return request.json()


def check_response(response):
    """Проверка ответа от API."""
    if type(response) is not dict:
        logger.error(
            f'Тип данных {type(response)} не соответствует ожидаемым.'
        )
        raise TypeError(
            f'Тип данных {type(response)} не соответствует ожидаемым.'
        )
    if 'homeworks' not in response:
        logger.error(
            'В ответе API отсутствует обязательный ключ "homeworks".'
        )
        raise TypeError(
            'В ответе API отсутствует обязательный ключ "homeworks".'
        )
    homeworks = response['homeworks']
    if response['homeworks'] != list(homeworks):
        logger.error(
            f'Тип данных {type(homeworks)} не соответствует ожидаемым.')
        raise TypeError(
            f'Тип данных {type(homeworks)} не соответствует ожидаемым')


def parse_status(homework):
    """Сообщение о статусе работы."""
    if 'homework_name' not in homework:
        logger.error('Отсутствует обязательный ключ "homework_name".')
        raise TypeError('Отсутствует обязательный ключ "homework_name".')
    homework_name = homework['homework_name']
    if homework['status'] not in HOMEWORK_VERDICTS:
        logger.error('Получен пустой или неожиданный статус работы.')
        raise TypeError('Получен пустой или неожиданный статус работы.')
    verdict = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    status = None
    current_status = None

    while True:
        try:
            homework = get_api_answer(timestamp - RETRY_PERIOD)
            check_response(homework)
            status = homework['homeworks'][0]['status']
            if status != current_status:
                message = parse_status(homework['homeworks'][0])
                send_message(bot, message)
            current_status = homework['homeworks'][0]['status']
            timestamp = homework['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

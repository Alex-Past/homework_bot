import logging
import os
import sys
import time
from contextlib import suppress
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

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
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(funcName)s - %(lineno)d - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверка наличия токенов."""
    tokens = [
        'PRACTICUM_TOKEN',
        'TELEGRAM_TOKEN',
        'TELEGRAM_CHAT_ID'
    ]
    missing_tokens = [t for t in tokens if not globals()[t] or '']
    if len(missing_tokens) != 0:
        logger.critical(
            f'Отсутствуют переменные окружения: {missing_tokens}'
        )
        raise ValueError(
            f'Отсутствуют переменные окружения: {missing_tokens}'
        )


def send_message(bot, message):
    """Отправка сообщений."""
    logger.debug('Попытка отправки сообщения.')
    bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(timestamp):
    """Получение ответа API."""
    logger.debug('Попытка получить ответ API.')
    payload = {'from_date': timestamp}
    try:
        request = requests.get(ENDPOINT,
                               headers=HEADERS,
                               params=payload)
    except requests.RequestException as error:
        (f'Ошибка ответа API: {error}')
    if request.status_code != HTTPStatus.OK:
        raise ValueError(f'Ошибка ответа API: {request.status_code}')
    logger.debug('Ответ API получен.')
    return request.json()


def check_response(response):
    """Проверка ответа от API."""
    logger.debug('Проверка ответа API.')
    if not isinstance(response, dict):
        raise TypeError(
            f'Тип данных "{type(response)}" в ответе API '
            'не соответствует ожидаемым.'
        )
    if 'homeworks' not in response:
        raise TypeError(
            'В ответе API отсутствует обязательный ключ "homeworks".'
        )
    homeworks = response['homeworks']
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            f'Тип данных "{type(homeworks)}" для ключа '
            '"homeworks" не соответствует ожидаемым.')
    logger.debug('Корректный ответ.')


def parse_status(homework):
    """Сообщение о статусе работы."""
    logger.debug('Попытка получить сообщение о статусе работы.')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует обязательный ключ "homework_name".')
    homework_name = homework['homework_name']
    if homework.get('status') not in HOMEWORK_VERDICTS:
        raise ValueError('Получен неожиданный статус работы: '
                         '{status}.'.format(status=homework['status']))
    verdict = HOMEWORK_VERDICTS[homework['status']]
    logger.debug('Сообщение о статусе работы получено.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_message = ''

    while True:
        try:
            homework = get_api_answer(timestamp - RETRY_PERIOD)
            check_response(homework)
            if len(homework['homeworks']) != 0:
                current_homework = homework['homeworks']
                message = parse_status(current_homework[0])
                if message != current_message:
                    send_message(bot, message)
                    current_message = parse_status(current_homework[0])
        except telegram.error.TelegramError as error:
            logger.error(f'Ошибка отправки сообщения:{error}')
            timestamp = homework['current_date']

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)
            if message != f'Сбой в работе программы: {error}':
                with suppress(Exception):
                    send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

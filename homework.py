import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exeptions import ParsStatusError, TelegramError

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


def check_tokens():
    """Проверка доступности переменных окружения."""
    logging.info('Проверка токенов')
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        logging.debug('Попытка отправки сообщения в telegram')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Отправка сообщения в telegram')
    except telegram.error.TelegramError as error:
        logging.error(f'Не удалось отправить сообщение в telegram: {error}')
        raise TelegramError(error)


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logging.debug('Попытка отправки запроса к эндпоинту API-сервиса')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logging.debug('Отправлен запрос к эндпоинту API-сервиса')
    except requests.ConnectionError:
        message = 'Подключение к Интернету отсутствует'
        logging.error(message)
        raise ConnectionError(message)
    except Exception as error:
        message = f'Эндпоинт недоступен. Ошибка от сервера: {error}'
        logging.error(message)
        send_message(message)
    if response.status_code != HTTPStatus.OK:
        message = f'Код ответа не 200: {response.status_code}'
        logging.error(message)
        raise requests.exceptions.RequestException(message)
    try:
        return response.json()
    except json.JSONDecodeError:
        message = 'Что-то не так с Json'
        logging.error(message)
        send_message(message)


def check_response(response):
    """Проверка ответа API на корректность."""
    logging.info('Проверка ответа от API')
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response:
        raise KeyError('Отсутсвует ключ homeworks')
    if 'current_date' not in response:
        raise KeyError('Отсутствует ключ current_date')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Ответ API не является листом')
    return homeworks


def parse_status(homework):
    """Извлечение статуса работы."""
    logging.info('Проверка парсинга')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        message = f'Неизвестный статус работы: {homework_status}'
        logging.error(message)
        send_message(message)
        raise ParsStatusError(message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    message = 'Запущен бот по проверке задания'
    logging.info(message)
    send_message(bot, message)
    if not check_tokens():
        message = 'Не все переменные окружения на месте'
        logging.critical(message)
        sys.exit(message)
    current_timestamp = 1656633600
    old_homework_status = ''
    while True:
        try:
            all_homework = get_api_answer(current_timestamp)
            homework = check_response(all_homework)[0]
            homework_status = parse_status(homework)
            if homework_status != old_homework_status:
                old_homework_status = homework_status
                send_message(bot, homework_status)
                logging.info('Сообщение отправлено')
            else:
                logging.info('Нет новых статусов')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        encoding='UTF-8',
        format='%(asctime)s, %(levelname)s, %(message)s',
        filename='program.log')
    main()

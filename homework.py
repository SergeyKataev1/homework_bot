import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


class TelegramError(Exception):
    """Ошибка отправки сообщения в telegram."""

    pass


class ParsStatusError(Exception):
    """Ошибка статуса в парсинге."""

    pass


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
        logging.error('Подключение к Интернету отсутствует')
        raise ConnectionError('Подключение к Интернету отсутствует')
    except Exception as error:
        message = f'Эндпоинт недоступен. Ошибка от сервера: {error}'
        logging.error(message)
        send_message(message)
    if response.status_code != HTTPStatus.OK:
        logging.error(f'Код ответа не 200: {response.status_code}')
        raise requests.exceptions.RequestException(
            f'Код ответа не 200: {response.status_code}')
    try:
        return response.json()
    except json.JSONDecodeError:
        logging.error('Что-то не так с Json')
        send_message('Что-то не так с Json')


def check_response(response):
    """Проверка ответа API на корректность."""
    logging.info('Проверка ответа от API')
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response or 'current_date' not in response:
        raise KeyError('Отсутствует ключ')
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
    logging.info('Запущен бот по проверке задания')
    send_message(bot, 'Запущен бот по проверке задания')
    if not check_tokens():
        logging.critical('Не все переменные окружения на месте')
        sys.exit('Не все переменные окружения на месте')
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
            logging.error(f'Сбой в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
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

"""==============================Инициализация модулей====================================="""
import datetime
import aiosqlite
import asyncio
import logging
import requests
import json
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import (Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
                           InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery)
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

"""==============================Инициализация и настройка бота====================================="""
load_dotenv()
dp = Dispatcher()
bot = Bot(token=os.getenv('TOKEN'))
api_key = os.getenv('API_KEY')
base_url = 'http://api.weatherapi.com/v1'

logging.basicConfig(level=logging.INFO,
                    filename='bot.log',
                    filemode='w',
                    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

logger = logging.getLogger(__name__)


class Weather(StatesGroup):
    user_input = State()
    select_mode = State()


choice = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Прогноз на сегодня")],
                                     [KeyboardButton(text="Прогноз на завтра")]],
                           resize_keyboard=True,
                           input_field_placeholder='Выберите...')

to_main = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Вернуться', callback_data='to_main')]])

"""==============================Обработчики====================================="""
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    logger.info(f'Пользователь {message.from_user.username} запустил бота')
    await message.answer("Привет, я бот - погодный информер")
    await message.answer("Выберите прогноз", reply_markup=choice)
    await state.set_state(Weather.select_mode)


@dp.message(Weather.select_mode, F.text.lower().in_(['прогноз на сегодня', 'прогноз на завтра']))
async def weather_mode(message: Message, state: FSMContext):
    selected_mode = 'today' if message.text.lower() == 'прогноз на сегодня' else 'tomorrow'
    await state.update_data(select_mode=selected_mode)
    await state.set_state(Weather.user_input)
    await message.answer("Введите название города, информации о погоде которого Вам нужно узнать.\n"
                         "Учтите, что нужно написать правильно не допуская орфографических ошибок.\n"
                         "Не используйте никакие знаки препинания, а также спец. символы.", reply_markup=ReplyKeyboardRemove())


@dp.message(Weather.select_mode)
async def incorrect_mode(message: Message):
    await message.answer("Пожалуйста, выберите вариант из предложенных на клавиатуре.")


@dp.message(Weather.user_input)
async def get_city(message: Message, state: FSMContext):
    try:
        await state.update_data(user_input=message.text)
        data = await state.get_data()

        city = data['user_input']
        forecast_type = data['select_mode']
        username = message.from_user.username

        if data['select_mode'] == 'today':
            weather_info = await get_weather_now(data['user_input'])
            await message.answer(weather_info, reply_markup=to_main)
            logger.info(f'Пользователь {message.from_user.username} запросил погоду на сегодня в городе {city}')
        if data['select_mode'] == 'tomorrow':
            weather_info = await get_future_weather(data['user_input'])
            await message.answer(weather_info, reply_markup=to_main)
            logger.info(f'Пользователь {message.from_user.username} запросил погоду на завтра в городе {city}')

        await log_request(username, city,forecast_type)
        await state.clear()
    except Exception as e:
        logger.exception(f'Ошибка в процессе получения города: {e}')
        await message.answer("Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже.")
        await state.clear()


async def get_weather_now(city: str) -> str:
    """Получает информацию о погоде на сегодня для указанного города."""
    try:
        response = requests.get(f'{base_url}/current.json?key={api_key}&q={city}&lang=ru')
        response.raise_for_status()
        data = response.json()

        city = data['location']['name']
        last_update = data['current']['last_updated']
        state = data['current']['condition']['text']
        temperature_celsius = data['current']['temp_c']
        wind_speed = data['current']['wind_kph']

        return (
            f'Погода в городе {city}:\n'
            f'Состояние: {state}\n'
            f'Температура: {temperature_celsius}°C\n'
            f'Скорость ветра: {wind_speed}\n'
            f'Местное время: {last_update}'
        )

    except requests.exceptions.RequestException as e:
        logger.warning(f"Ошибка при запросе к API: {e}")
        return f"Ошибка при запросе, попробуйте ещё раз."
    except (KeyError, TypeError) as e:
        logger.warning(f"Ошибка при обработке данных: {e}. Вероятно пользователь неправильно ввёл город.")
        return f"Ошибка при обработке данных: {e}. Проверьте правильность названия города"
    except json.JSONDecodeError as e:
        logger.warning(f"Ошибка при парсинге JSON: {e}")
        return f"Ошибка, попробуйте ещё раз."


async def get_future_weather(city: str) -> str:
    """Получает информацию о погоде на завтра для указанного города."""
    try:
        response = requests.get(f'{base_url}/forecast.json?key={api_key}&q={city}&lang=ru&days=2')
        response.raise_for_status()
        data = response.json()

        city = data['location']['name']
        forecast_day = data['forecast']['forecastday'][1]
        date = forecast_day['date']
        condition = forecast_day['day']['condition']['text']
        temperature_celsius = forecast_day['day']['avgtemp_c']

        return (
            f"Погода на завтра ({date}) в городе {city}:\n"
            f"Состояние: {condition}\n"
            f"Средняя температура: {temperature_celsius}°C"
        )


    except requests.exceptions.RequestException as e:
        logger.warning(f"Ошибка при запросе к API: {e}")
        return f"Ошибка при запросе, попробуйте ещё раз."
    except (KeyError, TypeError) as e:
        logger.warning(f"Ошибка при обработке данных: {e}. Вероятно пользователь неправильно ввёл город.")
        return f"Ошибка при обработке данных: {e}. Проверьте правильность названия города"
    except json.JSONDecodeError as e:
        logger.warning(f"Ошибка при парсинге JSON: {e}")
        return f"Ошибка, попробуйте ещё раз."


@dp.callback_query(F.data == 'to_main')
async def to_main_menu(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer("Возвращаю в главное меню...")
    await asyncio.sleep(2)
    await cmd_start(callback_query.message, state)


"""==============================База данных====================================="""
async def create_db():
    try:
        async with aiosqlite.connect('bot.db') as db:
                await db.execute('''
                CREATE TABLE IF NOT EXISTS statistics (
                    user_name TEXT,
                    city TEXT,
                    date TEXT,
                    forecast_type TEXT
                    )
                ''')
                await db.commit()
        logger.info("База данных успешно создана или уже существует")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при создании базы данных: {e}")


async def log_request(username: str, city: str, forecast_type: str) -> None:
    date = datetime.datetime.now()
    try:
        async with aiosqlite.connect('bot.db') as db:
            await db.execute(
                "INSERT INTO statistics (user_name, city, date, forecast_type) VALUES (?, ?, ?, ?)",
                (username, city, date, forecast_type)
            )
            await db.commit()
        logger.info(f"Запрос пользователя {username} успешно залогирован")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при логировании запроса: {e}")


"""==============================Запуск бота====================================="""
async def main():
    await create_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        logger.info("Бот запущен")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот отключен")

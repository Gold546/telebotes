import logging
import aiogram
import asyncio
import aiohttp

from config import Token

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Импортируем наш модуль работы с БД и сразу инициализируем таблицы
import sql

sql.init_db()


class DreamAnalis(StatesGroup):
    waiting_dream = State()
    waiting_emotion = State()
    waiting_raiting = State()


bot = Bot(Token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


@dp.message(Command("start"), StateFilter(None))
async def cmd_start(message: Message):
    # Сохраняем или обновляем пользователя в БД при старте бота
    sql.save_user(user_id=message.from_user.id, username=message.from_user.username)

    await message.answer(
        "🌙 Добро пожаловать в Morpheuz! 🌙\n\n"
        "Я твой персональный гид по миру подсознания. Вместе мы сможем:\n"
        "✨ Разгадывать сны — находить тайные смыслы и знаки.\n"
        "🌕 Следить за Луной — узнавать лунные дни и их влияние на твою жизнь.\n"
        "⏰ Просыпаться легко — рассчитывать идеальное время сна с умным будильником.\n\n"
        "👇 Быстрые команды (всегда доступны в меню или через /help):\n"
        "🔮 /dream — записать и проанализировать сон\n"
        "🌕 /moon — узнать текущий лунный день\n"
        "⏰ /alarm — настроить умный будильник\n"
        "❓ /help — открыть справку\n\n"
        "_Спи спокойно. Просыпайся бодрым вместе с Morpheuz ✨_"
    )


@dp.message(Command("cancel"),
            StateFilter(DreamAnalis.waiting_dream, DreamAnalis.waiting_emotion, DreamAnalis.waiting_raiting))
async def stoping(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🚫 Запись сна остановлена. Твой черновик сброшен, ты можете использовать любые другие команды.")


@dp.message(Command("dream"), StateFilter(None))
async def cmd_dream(message: Message, state: FSMContext):
    await state.set_state(DreamAnalis.waiting_dream)
    await message.answer(
        "Расскажи мне свой сон. Постарайся вспомнить как можно больше деталей: сюжет, яркие образы, людей, места или странные знаки 👇"
    )


@dp.message(StateFilter(DreamAnalis.waiting_dream), ~F.text.startswith('/'))
async def proces_dream(message: Message, state: FSMContext):
    await state.update_data(dream=message.text)
    await message.answer(
        "✅ Сюжет записан!\n\n"
        "🎭 А теперь поделись своими ощущениями. Какие эмоции ты испытывал внутри сна или сразу после пробуждения? (Например: _тревога, радость, умиротворение, страх, удивление_)"
    )
    await state.set_state(DreamAnalis.waiting_emotion)


@dp.message(StateFilter(DreamAnalis.waiting_emotion), ~F.text.startswith('/'))
async def proces_emotes(message: Message, state: FSMContext):
    await state.update_data(emoties=message.text)
    await message.answer(
        "🔮 Твои эмоции приняты!\nНачинаю связывать нити подсознания, расшифровка скоро будет готова...")
    await message.answer(
        "Оставьте отзыв на разбор сна, это очень поможет нашему развитию (1-10)")
    await state.set_state(DreamAnalis.waiting_raiting)


@dp.message(StateFilter(DreamAnalis.waiting_raiting), ~F.text.startswith('/'))
async def proces_raiting(message: Message, state: FSMContext):
    # Метод .strip() убирает случайные пробелы по краям ввода
    text = message.text.strip()

    # Проверяем, число ли это и попадает ли оно в рамки от 1 до 10
    if not text.isdigit() or not (1 <= int(text) <= 10):
        await message.answer("⚠️ Пожалуйста, введи только число от 1 до 10!")
        return

    await state.update_data(raiting=text)

    # Получаем все сохраненные в FSM данные по сну
    user_data = await state.get_data()
    dream_text = user_data.get('dream')
    emotions_text = user_data.get('emoties')
    raiting_text = user_data.get('raiting')

    # Записываем всё в базу данных SQLite
    sql.save_dream(
        user_id=message.from_user.id,
        dream=dream_text,
        emotions=emotions_text,
        raiting=raiting_text
    )

    await message.answer("🔮 Твой сон и отзыв успешно сохранены в подсознании Morpheuz. Спасибо!")
    await state.clear()
    await cmd_start(message)

@dp.message(StateFilter(DreamAnalis.waiting_dream, DreamAnalis.waiting_emotion, DreamAnalis.waiting_raiting),
            F.text.startswith('/'))
async def stoping_check(message: Message, state: FSMContext):
    await message.answer(
        "⚠️ Внимание! Сейчас идет запись сна.\n\n"
        "Пожалуйста, заверши опрос или введи команду /cancel, чтобы прервать процесс."
    )


@dp.message(Command("alarm"), StateFilter(None))
async def cmd_alarm(message: Message):
    await message.answer(
        "⏰ Умный будильник Morpheuz\n\n"
        "Эта функция уже создается! Совсем скоро я научусь высчитывать 90-минутные фазы сна, чтобы ты вставал с постели с максимальным зарядом энергии. Жди обновлений! 🚀"
    )


async def get_moon_data():
    url = "http://api.weatherapi.com/v1/astronomy.json?key=2c3d17321df24fd593c200600260507&q=Minsk"

    Moon_phase_ruski = {
        "New Moon": "Новолуние 🌑",
        "Waxing Crescent": "Растущая серповидная Луна 🌒",
        "First Quarter": "Первая четверть 🌓",
        "Waxing Gibbous": "Растущая Луна 🌔",
        "Full Moon": "Полнолуние 🌕",
        "Waning Gibbous": "Убывающая Луна 🌖",
        "Last Quarter": "Последняя четверть 🌗",
        "Waning Crescent": "Стареющая серповидная Луна 🌘"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()

            luna_phase = data['astronomy']['astro']['moon_phase']
            illumination = data['astronomy']['astro']['moon_illumination']

            luna_new = Moon_phase_ruski.get(luna_phase, luna_phase)

            return f"фаза луны: {luna_new} освещение: {illumination}%"


@dp.message(Command("moon"), StateFilter(None))
async def cmd_moon(message: Message):
    lunar_text = await get_moon_data()
    await message.answer(
        f"🌕 Лунный календарь\n"
        f"{lunar_text}"
    )


@dp.message(Command("help"), StateFilter(None))
async def cmd_help(message: Message):
    await message.answer(
        "❓ Справка по командам Morpheuz\n\n"
        "🔮 /dream — запустить пошаговый опрос для записи и толкования твоего сна.\n"
        "🌕 /moon — посмотреть текущую фазу луны и астрологический прогноз.\n"
        "⏰ /alarm — рассчитать циклы сна для бодрого утра.\n"
        "🚫 /cancel — прервать запись сна (работает только во время опроса)."
    )


@dp.message()
async def random_message(message: Message):
    await message.answer(
        "Я не совсем понял эту команду. Загляни в меню или введи /help, чтобы посмотреть список доступных действий.")


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')
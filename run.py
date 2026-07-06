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

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

class DreamAnalis(StatesGroup):
    waiting_dream = State()
    waiting_emotion = State()
    waiting_alarm_time = State()


bot = Bot(Token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
alarmer = AsyncIOScheduler()


@dp.message(Command("start"), StateFilter(None))
async def cmd_start(message: Message):
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


@dp.message(Command("cancel"), StateFilter(DreamAnalis.waiting_dream, DreamAnalis.waiting_emotion))
async def stoping(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🚫 Запись сна остановлена. Твой черновик сброшен, ты можешь использовать любые другие команды.")



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


    await state.clear()




@dp.message(StateFilter(DreamAnalis.waiting_dream, DreamAnalis.waiting_emotion), F.text.startswith('/'))
async def stoping_check(message: Message, state: FSMContext):
    await message.answer(
        "⚠️ Внимание! Сейчас идет запись сна.\n\n"
        "Пожалуйста, заверши опрос или введи команду /cancel, чтобы прервать процесс."
    )



async def wakeUp(chat_id: int):
    await bot.send_message(chat_id, "Пора вставать!!!")

@dp.message(Command("alarm"), StateFilter(None))
async def alarm(message: Message, state: FSMContext):
    await state.set_state(DreamAnalis.waiting_alarm_time)
    await message.answer(
            "⏰ Умный будильник Morpheuz\n\n"
            "Введи время пробуждения 🚀"
    )

@dp.message(StateFilter(DreamAnalis.waiting_alarm_time))
async def set_alarm(message: Message, state: FSMContext):
        alarm_time = datetime.strptime(message.text, "%H:%M").time()

        now = datetime.now()

        alarm_datetime = datetime.combine(now.date(), alarm_time)

        if alarm_datetime <= now:
             alarm_datetime += timedelta(days=1)

        alarmer.add_job(
                wakeUp,
                trigger="date",
                run_date=alarm_datetime,
                args=[message.chat.id]
        )

        await message.answer(
                f"⏰ Будильник установлен на:\n"
                f"{alarm_datetime.strftime('%d.%m.%Y %H:%M')}"
        )

        await state.clear()
#луна мабой

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

            luna_phase=data['astronomy']['astro']['moon_phase']
            illumination=data['astronomy']['astro']['moon_illumination']

            luna_new=Moon_phase_ruski.get(luna_phase)

            return f"фаза луны: {luna_new} освещение:  {illumination}"

@dp.message(Command("moon"), StateFilter(None))
async def cmd_moon(message: Message):
    lunar_text= await get_moon_data()

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
    alarmer.start()
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')
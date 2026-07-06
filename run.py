import logging
import aiogram
import asyncio
import aiohttp

from openai import AsyncOpenAI
import httpx

from config import Token, AI_TOKEN
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

# Импортируем нашу базу данных и создаем таблицы
import sql

sql.init_db()

base_url = "https://openrouter.ai/api/v1"

if not AI_TOKEN:
    raise ValueError("Критическая ошибка: AI_TOKEN (API-ключ OpenRouter) пустой!")

ai_client = AsyncOpenAI(
    api_key=AI_TOKEN,
    base_url=base_url
)

STATIC_FALLBACK_MODELS = [
    "meta-llama/llama-3-8b-instruct:free",
    "google/gemini-2.5-flash:free",
    "google/gemma-2-9b-it:free",
    "mistralai/mistral-7b-instruct:free",
    "qwen/qwen-2-7b-instruct:free"
]


async def fetch_live_free_models() -> list[str]:
    try:
        clean_url = base_url.split("/v1")[0] + "/v1/models"
        async with httpx.AsyncClient() as client:
            response = await client.get(clean_url, timeout=4)
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                free_ids = [m["id"] for m in models if m.get("id", "").endswith(":free")]
                if free_ids:
                    return free_ids
    except Exception as e:
        logging.warning(f"Не удалось динамически обновить список моделей OpenRouter: {e}")
    return STATIC_FALLBACK_MODELS


class DreamAnalis(StatesGroup):
    waiting_dream = State()
    waiting_emotion = State()
    waiting_raiting = State()
    waiting_alarm_time = State()


bot = Bot(Token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
alarmer = AsyncIOScheduler()


@dp.message(Command("start"), StateFilter(None))
async def cmd_start(message: Message):
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
            StateFilter(DreamAnalis.waiting_dream, DreamAnalis.waiting_emotion, DreamAnalis.waiting_raiting,
                        DreamAnalis.waiting_alarm_time))
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


# ШАГ 3: Получаем эмоции и СРАЗУ вызываем ИИ (без промежуточного отзыва!)
@dp.message(StateFilter(DreamAnalis.waiting_emotion), ~F.text.startswith('/'))
async def proces_emotes(message: Message, state: FSMContext):
    await state.update_data(emoties=message.text)

    await message.answer("🔮 Твои эмоции приняты!")
    waiting_msg = await message.answer("🧠 Начинаю анализ твоего сна... Это может занять несколько секунд.")

    user_data = await state.get_data()
    dream_text = user_data.get('dream')
    emotions_text = user_data.get('emoties')

    prompt = f"Сюжет сна: {dream_text}\nЭмоции пользователя: {emotions_text}"
    available_models = await fetch_live_free_models()
    preferred_model = "meta-llama/llama-3-8b-instruct:free"

    if preferred_model in available_models:
        available_models.remove(preferred_model)
    available_models.insert(0, preferred_model)

    ai_text = None
    last_error = "Список моделей пуст"

    for model_name in available_models:
        try:
            logging.info(f"Запрос отправлен в бесплатную модель: {model_name}")
            response = await ai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты — тёплый, мудрый и внимательный психолог сна по имени MorpheuZ. "
                            "Помоги пользователю понять его сон. Твой ответ должен состоять строго из трех разделов:\n\n"
                            "✨ <b>Анализ твоего сна:</b>\n"
                            "🔮 <b>Толкование:</b>\n(Напиши здесь теплое толкование сна на 3-4 предложения, связывая сюжет с эмоциями человека в реальной жизни)\n\n"
                            "🌅 <b>Утренний вызов:</b>\n(Придумай одно простое физическое или ментальное задание на сегодня, вдохновленное этим сном)\n\n"
                            "💡 <b>Совет:</b>\n(Дай короткую финальную рекомендацию или мотивацию в 1 предложение)\n\n"
                            "Отвечай обычным текстом с использованием указанных HTML-тегов для жирного шрифта. Никакого JSON кода строить не нужно!"
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=900,
                extra_headers={
                    "HTTP-Referer": "https://localhost",
                    "X-Title": "MorpheuZ Sleep Bot"
                }
            )

            ai_text = response.choices[0].message.content
            if ai_text:
                break

        except Exception as e:
            last_error = str(e)
            logging.warning(f"⚠️ Сбой бесплатной модели {model_name}: {last_error}")
            continue

    try:
        await waiting_msg.delete()

        if ai_text:
            # Выводим готовый красивый разбор от ИИ
            await message.answer(ai_text, parse_mode="HTML")

            # Переводим в состояние ожидания отзыва ОКОНЧАТЕЛЬНО
            await message.answer("✨ Разбор готов! Оцени, пожалуйста, насколько полезным был этот анализ (от 1 до 10):")
            await state.set_state(DreamAnalis.waiting_raiting)
        else:
            await message.answer(
                f"🛑 <b>Ошибка сети ИИ:</b> ни одна из доступных моделей не ответила.\n"
                f"<i>Лог ошибки: {last_error}</i>"
            )
            await state.clear()
            await cmd_start(message)

    except Exception as e:
        logging.error(f"Ошибка при выводе ответа ИИ: {e}")
        await state.clear()


# ШАГ 4: Принимаем оценку ПОСЛЕ разбора и сохраняем всё в БД
@dp.message(StateFilter(DreamAnalis.waiting_raiting), ~F.text.startswith('/'))
async def proces_raiting(message: Message, state: FSMContext):
    text = message.text.strip()

    if not text.isdigit() or not (1 <= int(text) <= 10):
        await message.answer("⚠️ Пожалуйста, введи только число от 1 до 10!")
        return

    await state.update_data(raiting=text)

    user_data = await state.get_data()
    dream_text = user_data.get('dream')
    emotions_text = user_data.get('emoties')
    raiting_text = user_data.get('raiting')

    # Сохраняем в SQLite полный набор: сон + эмоции + финальную оценку разбора
    sql.save_dream(
        user_id=message.from_user.id,
        dream=dream_text,
        emotions=emotions_text,
        raiting=raiting_text
    )

    await message.answer("🔮 Твой сон и оценка успешно сохранены в подсознании Morpheuz. Спасибо за отзыв!")
    await state.clear()
    await cmd_start(message)


@dp.message(StateFilter(DreamAnalis.waiting_dream, DreamAnalis.waiting_emotion, DreamAnalis.waiting_raiting),
            F.text.startswith('/'))
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
        "Введи время пробуждения в формате ЧЧ:ММ (например, 07:30) 🚀"
    )


@dp.message(StateFilter(DreamAnalis.waiting_alarm_time))
async def set_alarm(message: Message, state: FSMContext):
    try:
        alarm_time = datetime.strptime(message.text.strip(), "%H:%M").time()

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
    except ValueError:
        await message.answer("⚠️ Неверный формат времени! Используй ЧЧ:ММ (например, 07:30)")


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
        "⏰ /alarm — настроить будильник.\n"
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
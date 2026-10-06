import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from openai import OpenAI

# ================= НАСТРОЙКИ (ВСТАВЬ СВОИ ДАННЫЕ) =================
# ================= НАСТРОЙКИ (ВСТАВЬ СВОИ ДАННЫЕ) =================
TELEGRAM_BOT_TOKEN = ""
OPENROUTER_API_KEY = ""
# =================================================================

# =================================================================

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Официальный client OpenAI, настроенный на OpenRouter
ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Профили бота
BOT_PROFILES = {
    "helper": {
        "title": "📚 Помощник по учебе",
        "system": "Ты — профессиональный академический помощник. Твоя цель — помогать студенту в учебе, объяснять сложные термины простыми словами, помогать решать задачи. Отвечай кратко, информативно и по делу."
    },
    "medbot": {
        "title": "🩺 Медбот (Консультант)",
        "system": "Ты — виртуальный медицинский консультант. Отвечай вежливо, давай общую справочную информацию о здоровье и симптомах. Важно: всегда в конце ответа делай короткую приписку, что это не является официальным диагнозом и нужно обратиться к врачу."
    },
    "general": {
        "title": "🤖 Обычный ассистент",
        "system": "Ты — дружелюбный и полезный ИИ-помощник общего профиля. Готов поддержать любую тему, шутить и отвечать на любые вопросы пользователя."
    }
}


def get_profiles_keyboard():
    builder = InlineKeyboardBuilder()
    for key, profile in BOT_PROFILES.items():
        builder.button(text=profile["title"], callback_data=f"set_profile:{key}")
    builder.adjust(1)
    return builder.as_markup()


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.update_data(profile="general", history=[])
    welcome_text = (
        "👋 Привет! Я чат-бот со встроенной нейросетью OpenRouter.\n\n"
        "🧠 Я помню контекст общения.\n"
        "🔄 /reset — очистить память диалога.\n"
        "🎭 /change — сменить характер/профиль бота.\n\n"
        "По умолчанию включен режим: Обычный ассистент.\n"
        "Можешь задавать свой вопрос!"
    )
    await message.answer(welcome_text)


@dp.message(Command("reset"))
async def cmd_reset(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    current_profile = user_data.get("profile", "general")
    await state.update_data(history=[])
    profile_title = BOT_PROFILES.get(current_profile, {}).get("title", "Обычный ассистент")
    await message.answer(f"🧹 Память диалога успешно очищена!\nТекущий режим: {profile_title}")


@dp.message(Command("change"))
async def cmd_change(message: types.Message):
    await message.answer("Выбери профиль и характер для нейросети:", reply_markup=get_profiles_keyboard())


@dp.callback_query(F.data.startswith("set_profile:"))
async def process_profile_callback(callback: types.CallbackQuery, state: FSMContext):
    profile_key = callback.data.split(":")[1]

    if profile_key in BOT_PROFILES:
        await state.update_data(profile=profile_key, history=[])
        selected_title = BOT_PROFILES[profile_key]["title"]
        await callback.message.edit_text(
            text=f"🎭 Успешно переключено на режим: {selected_title}!\nПамять диалога очищена. Задавай вопрос!"
        )
    await callback.answer()


@dp.message(F.text)
async def handle_message(message: types.Message, state: FSMContext):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    user_data = await state.get_data()
    current_profile = user_data.get("profile", "general")
    history = user_data.get("history", [])

    if current_profile not in BOT_PROFILES:
        current_profile = "general"

    system_prompt = BOT_PROFILES[current_profile]["system"]

    history.append({"role": "user", "content": message.text})
    if len(history) > 10:
        history = history[-10:]

    messages_to_send = [{"role": "system", "content": system_prompt}] + history

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: ai_client.chat.completions.create(
                model="openrouter/free",  # Поставил общий пул, чтобы не было ошибок перегрузки 429
                messages=messages_to_send
            )
        )

        ai_response = response.choices[0].message.content

        # Защита от пустого ответа
        if not ai_response:
            ai_response = "Извини, не удалось сгенерировать текст. Попробуй еще раз."

        # Сохраняем чистый ответ в историю
        history.append({"role": "assistant", "content": ai_response})
        await state.update_data(history=history)

        # ОТПРАВЛЯЕМ СТРОГО ТЕКСТ НЕЙРОСЕТИ БЕЗ ВСЯКОГО МУСОРА И КРИВОЙ РАЗМЕТКИ
        await message.answer(ai_response)

    except Exception as e:
        logging.error(f"Ошибка OpenRouter API: {e}")
        await message.answer("⚠️ Не удалось получить ответ от нейросети. Сбросьте контекст командой /reset.")


async def main():
    print("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

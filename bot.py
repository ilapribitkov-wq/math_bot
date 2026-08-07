import logging
import os
import datetime
import asyncio
import traceback
import base64
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, OPENROUTER_API_KEY
from solver import solve_math, plot_function, transcribe_voice
from database import init_db, get_user, create_user, save_history, get_history, clear_history, activate_subscription
import subprocess
import os

# Устанавливаем FFmpeg, если его нет
try:
    subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
except:
    print("⚠️ FFmpeg не найден, устанавливаю...")
    os.system("apt-get update && apt-get install -y ffmpeg")
    print("✅ FFmpeg установлен")

# ===== ВСТАВЬ СВОЙ ID (число) =====
ADMIN_ID = 7827158843  # ЗАМЕНИ НА СВОЙ!

logging.basicConfig(level=logging.INFO)

def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Решить задачу", callback_data="solve")],
        [InlineKeyboardButton("💳 Оплатить подписку", callback_data="pay")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
        [InlineKeyboardButton("⚛️ Физика", callback_data="physics")],
        [InlineKeyboardButton("📊 График", callback_data="graph")],
        [InlineKeyboardButton("🧪 Химия", callback_data="chemistry")],
        [InlineKeyboardButton("📚 История", callback_data="history")],
        [InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user = await get_user(user_id)
        if not user:
            await create_user(user_id)
            user = await get_user(user_id)
        trial_start = user[2] if user else None
        days_left = 2
        if trial_start:
            trial_date = datetime.datetime.strptime(trial_start, "%Y-%m-%d").date()
            days_used = (datetime.datetime.now().date() - trial_date).days
            days_left = max(0, 2 - days_used)
        await update.message.reply_text(
            f"🤖 Привет! Я решаю задачи по математике, физике и химии.\n"
            f"📸 Отправь фото с задачей\n🎤 Отправь голосовое сообщение\n"
            f"⏳ Осталось дней бесплатного доступа: {days_left}",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        print(f"❌ Ошибка в start: {e}")

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 Оплата:\n"
        "Переведи 200 ₽ на карту: 1234 5678 9012 3456\n"
        "После оплаты напиши мне в ЛС: @your_support"
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        records = await get_history(user_id, limit=10)
        if not records:
            await update.message.reply_text("📭 Нет сохранённых решений.")
            return
        text = "📚 <b>Последние 10 решений:</b>\n\n"
        for i, (query, answer, created_at) in enumerate(records, 1):
            short = answer[:200] + "..." if len(answer) > 200 else answer
            text += f"{i}. ❓ {query}\n   ✅ {short}\n   🕐 {created_at[:16]}\n\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"❌ Ошибка в history: {e}")

async def clear_history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        await clear_history(user_id)
        await update.message.reply_text("🗑️ История очищена.")
    except Exception as e:
        print(f"❌ Ошибка в clear_history: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text.lower().strip()

        # ГРАФИК
        if text.startswith("график") or text.startswith("graph"):
            expr = update.message.text.replace("график", "").replace("graph", "").strip()
            if not expr:
                await update.message.reply_text("📊 Напиши функцию, например: график x**2")
                return
            img = plot_function(expr)
            if img:
                await update.message.reply_photo(photo=img, caption=f"📈 График: {expr}")
            else:
                await update.message.reply_text("❌ Ошибка построения графика")
            return

        # АДМИН — БЕЗЛИМИТ
        if user_id == ADMIN_ID:
            solution = solve_math(update.message.text)
            await save_history(user_id, update.message.text, solution)
            await update.message.reply_text(f"📝 Решение:\n\n{solution}")
            return

        # ОБЫЧНЫЕ ПОЛЬЗОВАТЕЛИ (2 дня бесплатно)
        user = await get_user(user_id)
        if not user:
            await create_user(user_id)
            user = await get_user(user_id)

        subscription_end = user[1]
        trial_start = user[2]

        if subscription_end and datetime.datetime.now().date() < datetime.datetime.strptime(subscription_end, "%Y-%m-%d").date():
            solution = solve_math(update.message.text)
            await save_history(user_id, update.message.text, solution)
            await update.message.reply_text(f"📝 Решение:\n\n{solution}")
            return

        if trial_start:
            trial_date = datetime.datetime.strptime(trial_start, "%Y-%m-%d").date()
            days_used = (datetime.datetime.now().date() - trial_date).days
            if days_used < 2:
                solution = solve_math(update.message.text)
                await save_history(user_id, update.message.text, solution)
                days_left = 2 - days_used
                await update.message.reply_text(
                    f"📝 Решение:\n\n{solution}\n\n⏳ Осталось дней: {days_left}"
                )
                return

        await update.message.reply_text("❌ Бесплатный период закончился. Оплати подписку /pay")
    except Exception as e:
        print(f"❌ Ошибка в handle_message: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo_file = await update.message.photo[-1].get_file()
    file_path = "temp_photo.jpg"
    await photo_file.download_to_drive(file_path)

    try:
        with open(file_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Распознай текст с фото. Напиши только текст."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                }
            ]
        }
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        if "error" in result:
            await update.message.reply_text(f"❌ Ошибка: {result['error']['message']}")
            return
        text = result['choices'][0]['message']['content'].strip()
        os.remove(file_path)

        if not text or len(text) < 3:
            await update.message.reply_text("❌ Не удалось распознать текст.")
            return

        if user_id == ADMIN_ID:
            solution = solve_math(text)
            await save_history(user_id, text, solution)
            await update.message.reply_text(f"📸 Распознано:\n{text}\n\n📝 Решение:\n{solution}")
            return

        user = await get_user(user_id)
        if not user:
            await create_user(user_id)
            user = await get_user(user_id)

        subscription_end = user[1]
        trial_start = user[2]

        if subscription_end and datetime.datetime.now().date() < datetime.datetime.strptime(subscription_end, "%Y-%m-%d").date():
            solution = solve_math(text)
            await save_history(user_id, text, solution)
            await update.message.reply_text(f"📸 Распознано:\n{text}\n\n📝 Решение:\n{solution}")
            return

        if trial_start:
            trial_date = datetime.datetime.strptime(trial_start, "%Y-%m-%d").date()
            days_used = (datetime.datetime.now().date() - trial_date).days
            if days_used < 2:
                solution = solve_math(text)
                await save_history(user_id, text, solution)
                days_left = 2 - days_used
                await update.message.reply_text(
                    f"📸 Распознано:\n{text}\n\n📝 Решение:\n{solution}\n\n⏳ Осталось дней: {days_left}"
                )
                return

        await update.message.reply_text("❌ Бесплатный период закончился. Оплати подписку /pay")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    voice_file = await update.message.voice.get_file()
    file_path = f"voice_{user_id}.ogg"
    await voice_file.download_to_drive(file_path)

    await update.message.reply_text("🎤 Распознаю голос...")
    text = transcribe_voice(file_path)

    # 👇 УДАЛЯЕМ ФАЙЛ ТОЛЬКО ЗДЕСЬ (ОДИН РАЗ)
    if os.path.exists(file_path):
        os.remove(file_path)

    if not text:
        await update.message.reply_text("❌ Не удалось распознать голос.")
        return

    await update.message.reply_text(f"📝 Распознано:\n{text}")

    if user_id == ADMIN_ID:
        solution = solve_math(text)
        await save_history(user_id, text, solution)
        await update.message.reply_text(f"📝 Решение:\n\n{solution}")
        return

    user = await get_user(user_id)
    if not user:
        await create_user(user_id)
        user = await get_user(user_id)

    subscription_end = user[1]
    trial_start = user[2]

    if subscription_end and datetime.datetime.now().date() < datetime.datetime.strptime(subscription_end, "%Y-%m-%d").date():
        solution = solve_math(text)
        await save_history(user_id, text, solution)
        await update.message.reply_text(f"📝 Решение:\n\n{solution}")
        return

    if trial_start:
        trial_date = datetime.datetime.strptime(trial_start, "%Y-%m-%d").date()
        days_used = (datetime.datetime.now().date() - trial_date).days
        if days_used < 2:
            solution = solve_math(text)
            await save_history(user_id, text, solution)
            days_left = 2 - days_used
            await update.message.reply_text(
                f"📝 Решение:\n\n{solution}\n\n⏳ Осталось дней: {days_left}"
            )
            return

    await update.message.reply_text("❌ Бесплатный период закончился. Оплати подписку /pay")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "solve":
        await query.edit_message_text("✏️ Напиши задачу текстом, фото или голосом.")
    elif query.data == "pay":
        await query.edit_message_text("💳 Переведи 200 ₽ на карту: 1234 5678 9012 3456")
    elif query.data == "help":
        await query.edit_message_text("❓ Помощь:\n• Текст\n• Фото\n• Голос\n• График x**2")
    elif query.data == "physics":
        await query.edit_message_text("⚛️ Напиши задачу по физике.")
    elif query.data == "graph":
        await query.edit_message_text("📊 Напиши 'график x**2'")
    elif query.data == "chemistry":
        await query.edit_message_text("🧪 Напиши задачу по химии.")
    elif query.data == "history":
        await query.edit_message_text("📚 Напиши /history")
    elif query.data == "clear_history":
        await query.edit_message_text("🗑️ Напиши /clear_history")

def main():
    asyncio.run(init_db())
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("clear_history", clear_history_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("👁️ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()

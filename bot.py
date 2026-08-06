import logging
import os
import datetime
import asyncio
import traceback
import base64
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, OPENROUTER_API_KEY
from solver import solve_math, plot_function, transcribe_voice
from database import init_db, get_user, create_user, save_history, get_history, clear_history, activate_subscription

ADMIN_ID = 8875058913  # ВСТАВЬ СВОЙ ID!

logging.basicConfig(level=logging.INFO)

def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Решить задачу", callback_data="solve")],
        [InlineKeyboardButton("💳 Оплатить подписку", callback_data="pay")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
        [InlineKeyboardButton("⚛️ Физика", callback_data="physics")],
        [InlineKeyboardButton("📊 График", callback_data="graph")],
        [InlineKeyboardButton("🧪 Химия", callback_data="chemistry")],
        [InlineKeyboardButton("📚 История решений", callback_data="history")],
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
            f"📸 Отправь фото с задачей — я распознаю и решу!\n"
            f"🎤 Отправь голосовое сообщение — я распознаю и решу!\n"
            f"⏳ У тебя осталось {days_left} дней бесплатного доступа.\n"
            f"Выбери действие ниже:",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        print(f"❌ Ошибка в start: {e}")
        traceback.print_exc()

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 Оплата:\n"
        "Переведи 200 ₽ на карту: 1234 5678 9012 3456\n"
        "После оплаты напиши мне в ЛС: @your_support\n"
        "Я активирую подписку!"
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        records = await get_history(user_id, limit=10)
        if not records:
            await update.message.reply_text("📭 У тебя пока нет сохранённых решений.")
            return
        text = "📚 <b>Твои последние 10 решений:</b>\n\n"
        for i, (query, answer, created_at) in enumerate(records, 1):
            short_answer = answer[:200] + "..." if len(answer) > 200 else answer
            text += f"{i}. ❓ {query}\n   ✅ {short_answer}\n   🕐 {created_at[:16]}\n\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"❌ Ошибка в history: {e}")
        traceback.print_exc()

async def clear_history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        await clear_history(user_id)
        await update.message.reply_text("🗑️ История решений очищена.")
    except Exception as e:
        print(f"❌ Ошибка в clear_history: {e}")
        traceback.print_exc()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text.lower().strip()
        
        if text.startswith("график") or text.startswith("graph"):
            expr = update.message.text.replace("график", "").replace("graph", "").strip()
            if not expr:
                await update.message.reply_text("📊 Напиши функцию, например: график x**2")
                return
            img = plot_function(expr)
            if img:
                await update.message.reply_photo(photo=img, caption=f"📈 График функции: {expr}")
            else:
                await update.message.reply_text("❌ Не удалось построить график. Проверь формулу.")
            return
        
        if user_id == ADMIN_ID:
            solution = solve_math(update.message.text)
            await save_history(user_id, update.message.text, solution)
            await update.message.reply_text(f"📝 Решение:\n\n{solution}")
            return
        
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
                    f"📝 Решение:\n\n{solution}\n\n⏳ Осталось дней бесплатного периода: {days_left}"
                )
                return
        
        await update.message.reply_text(
            "❌ Твой бесплатный период (2 дня) закончился.\n"
            "Оплати подписку командой /pay"
        )
    except Exception as e:
        print(f"❌ Ошибка в handle_message: {e}")
        traceback.print_exc()

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo_file = await update.message.photo[-1].get_file()
    file_path = "temp_photo.jpg"
    await photo_file.download_to_drive(file_path)
    try:
        with open(file_path, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
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
                        {"type": "text", "text": "Распознай текст с этого фото. Напиши только сам текст, без пояснений."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                }
            ]
        }
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        if "error" in result:
            await update.message.reply_text(f"❌ Ошибка распознавания: {result['error']['message']}")
            return
        text = result['choices'][0]['message']['content'].strip()
        if os.path.exists(file_path):
            os.remove(file_path)
        if not text or len(text) < 3:
            await update.message.reply_text("❌ Не удалось распознать текст.")
            return
        if user_id == ADMIN_ID:
            solution = solve_math(text)
            await save_history(user_id, text, solution)
            await update.message.reply_text(f"📸 Распознанный текст:\n{text}\n\n📝 Решение:\n{solution}")
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
            await update.message.reply_text(f"📸 Распознанный текст:\n{text}\n\n📝 Решение:\n{solution}")
            return
        if trial_start:
            trial_date = datetime.datetime.strptime(trial_start, "%Y-%m-%d").date()
            days_used = (datetime.datetime.now().date() - trial_date).days
            if days_used < 2:
                solution = solve_math(text)
                await save_history(user_id, text, solution)
                days_left = 2 - days_used
                await update.message.reply_text(
                    f"📸 Распознанный текст:\n{text}\n\n📝 Решение:\n{solution}\n\n⏳ Осталось дней бесплатного периода: {days_left}"
                )
                return
        await update.message.reply_text("❌ Твой бесплатный период закончился. Оплати подписку.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при распознавании: {str(e)}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "solve":
        await query.edit_message_text("✏️ Напиши свою задачу текстом или отправь фото.")
    elif query.data == "pay":
        await query.edit_message_text("💳 Переведи 200 ₽ на карту: 1234 5678 9012 3456")
    elif query.data == "help":
        await query.edit_message_text("❓ Помощь:\n• Напиши задачу текстом\n• Отправь фото\n• Отправь голосовое")
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
    import asyncio
    asyncio.run(init_db())
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("clear_history", clear_history_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("👁️ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()

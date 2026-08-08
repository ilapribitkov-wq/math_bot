import logging
import os
import datetime
import asyncio
import base64
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, OPENROUTER_API_KEY
from solver import solve_math, plot_function
from database import (
    init_db, get_user, create_user, save_history, get_history, clear_history,
    activate_subscription, check_flood, check_daily_limit, check_pay_limit,
    check_complex_limit, block_ip, is_ip_blocked, get_ip_from_update, notify_admin,
    clean_old_records
)

ADMIN_ID = 7827158843  # ЗАМЕНИ НА СВОЙ

logging.basicConfig(level=logging.INFO)

def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Решить задачу", callback_data="solve")],
        [InlineKeyboardButton("💳 Оплатить подписку", callback_data="pay")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
        [InlineKeyboardButton("📊 График", callback_data="graph")],
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
            f"📸 Отправь фото с задачей\n"
            f"⏳ Осталось дней бесплатного доступа: {days_left}",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        print(f"❌ Ошибка в start: {e}")

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_pay_limit(user_id):
        await update.message.reply_text("❌ Ты уже использовал /pay 3 раза сегодня. Завтра снова.")
        return
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

        # ===== ЗАЩИТА: IP БЛОКИРОВКА =====
        ip = await get_ip_from_update(update)
        if ip and await is_ip_blocked(ip):
            await update.message.reply_text("❌ Твой IP заблокирован за нарушение правил.")
            return

        # ===== ГРАФИК =====
        if text.startswith("график") or text.startswith("graph"):
            expr = update.message.text.replace("график", "").replace("graph", "").strip()
            if not expr:
                await update.message.reply_text("📊 Напиши функцию, например: график x**2")
                return
            # Проверка лимита на сложные запросы
            if user_id != ADMIN_ID and not await check_complex_limit(user_id):
                await update.message.reply_text("❌ Ты исчерпал дневной лимит на сложные запросы (10).")
                return
            img = plot_function(expr)
            if img:
                await update.message.reply_photo(photo=img, caption=f"📈 График: {expr}")
            else:
                await update.message.reply_text("❌ Не удалось построить график. Проверь формулу.")
            return

        # ===== ЗАЩИТА: АНТИФЛУД И ДНЕВНОЙ ЛИМИТ =====
        if user_id != ADMIN_ID:
            if not await check_flood(user_id, cooldown=3):
                await update.message.reply_text("⏳ Подожди 3 секунды.")
                return
            if not await check_daily_limit(user_id, limit=100):
                await update.message.reply_text("❌ Ты исчерпал дневной лимит (100 запросов).")
                return

        # ===== АДМИН =====
        if user_id == ADMIN_ID:
            solution = solve_math(update.message.text)
            await save_history(user_id, update.message.text, solution)
            await update.message.reply_text(f"📝 Решение:\n\n{solution}")
            return

        # ===== ОБЫЧНЫЕ ПОЛЬЗОВАТЕЛИ =====
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

        await update.message.reply_text("❌ Бесплатный период закончился. /pay")
    except Exception as e:
        print(f"❌ Ошибка в handle_message: {e}")
        await update.message.reply_text("⚠️ Ошибка. Попробуй позже.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        photo_file = await update.message.photo[-1].get_file()
        file_path = "temp_photo.jpg"
        await photo_file.download_to_drive(file_path)

        with open(file_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')
        os.remove(file_path)

        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "openai/gpt-4o-mini",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Распознай текст с фото. Напиши только текст."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            }]
        }
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        result = response.json()
        text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not text:
            await update.message.reply_text("❌ Не удалось распознать текст.")
            return

        if user_id != ADMIN_ID:
            if not await check_flood(user_id, 3):
                await update.message.reply_text("⏳ Подожди 3 секунды.")
                return
            if not await check_daily_limit(user_id, 100):
                await update.message.reply_text("❌ Дневной лимит исчерпан.")
                return

        if user_id == ADMIN_ID:
            solution = solve_math(text)
            await save_history(user_id, text, solution)
            await update.message.reply_text(f"📸 Распознано:\n{text}\n\n📝 {solution}")
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
            await update.message.reply_text(f"📸 {text}\n\n📝 {solution}")
            return
        if trial_start:
            trial_date = datetime.datetime.strptime(trial_start, "%Y-%m-%d").date()
            days_used = (datetime.datetime.now().date() - trial_date).days
            if days_used < 2:
                solution = solve_math(text)
                await save_history(user_id, text, solution)
                days_left = 2 - days_used
                await update.message.reply_text(f"📸 {text}\n\n📝 {solution}\n⏳ Дней: {days_left}")
                return

        await update.message.reply_text("❌ Бесплатный период закончился.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "solve":
        await query.edit_message_text("✏️ Напиши задачу текстом или отправь фото.")
    elif query.data == "pay":
        await query.edit_message_text("💳 Переведи 200 ₽ на карту: 1234 5678 9012 3456")
    elif query.data == "help":
        await query.edit_message_text("❓ Текст, фото, график x**2")
    elif query.data == "graph":
        await query.edit_message_text("📊 Напиши 'график x**2'")
    elif query.data == "history":
        await query.edit_message_text("📚 /history")
    elif query.data == "clear_history":
        await query.edit_message_text("🗑️ /clear_history")
    elif query.data == "physics":
        await query.edit_message_text(
        "⚛️ Физика:\n\n"
        "Напиши задачу по физике, например:\n"
        "• 'С какой силой притягиваются два тела массами 10 и 20 кг на расстоянии 2 м?'\n"
        "• 'Найди импульс тела массой 5 кг со скоростью 10 м/с'\n"
        "• 'Чему равна кинетическая энергия тела массой 2 кг при скорости 3 м/с?'"
    )

    elif query.data == "chemistry":
        await query.edit_message_text(
        "🧪 Химия:\n\n"
        "Напиши задачу по химии, например:\n"
        "• 'Уравняй реакцию: H2 + O2 = H2O'\n"
        "• 'Найди молярную массу NaOH'\n"
        "• 'Рассчитай pH раствора HCl 0.1M'"
    )

def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Решить задачу", callback_data="solve")],
        [InlineKeyboardButton("💳 Оплатить подписку", callback_data="pay")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
        [InlineKeyboardButton("⚛️ Физика", callback_data="physics")],
        [InlineKeyboardButton("🧪 Химия", callback_data="chemistry")],
        [InlineKeyboardButton("📊 График", callback_data="graph")],
        [InlineKeyboardButton("📚 История", callback_data="history")],
        [InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history")],
    ]
    return InlineKeyboardMarkup(keyboard)
def main():
    print("🚀 Бот запускается с защитой!")
    asyncio.run(init_db())
    asyncio.run(clean_old_records())
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("clear_history", clear_history_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("👁️ Бот запущен! Защита активна.")
    app.run_polling()

if __name__ == "__main__":
    main()

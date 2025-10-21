# walshop_bot.py
# Requires: python-telegram-bot (v20+), Python 3.10+
# Usage: set TOKEN and ADMIN_ID below, then run the file.

import json
import logging
from pathlib import Path
from typing import Dict, Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

# ----------------- CONFIG -----------------
TOKEN = "8347151872:AAEaFx5tORqVUgTf1lEdcEfbY0sUfEt470k"
ADMIN_ID = 7004027230  # <-- آی‌دی تلگرام ادمین (عدد)
DATA_FILE = Path("data.json")
BOT_NAME = "وال شاپ"
# ------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# conversation states
(
    CHOOSING_ACTION,
    COLLECT_CARD_NAME,
    COLLECT_CARD_NUMBER,
) = range(3)


# ---------- simple data storage ----------
def load_data() -> Dict[str, Any]:
    if not DATA_FILE.exists():
        return {"users": {}, "orders": {}}
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_data(data: Dict[str, Any]):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


data = load_data()


def ensure_user(user_id: int, username: str | None, full_name: str) -> Dict[str, Any]:
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"username": username, "full_name": full_name, "orders": []}
        save_data(data)
    return data["users"][uid]


# ---------- keyboards ----------
def main_menu_keyboard():
    kb = [
        [KeyboardButton("🛍 خرید تلگرام پریمیوم")],
        [KeyboardButton("🎁 خرید گیفت"), KeyboardButton("⭐ خرید ستاره")],
        [KeyboardButton("👤 حساب کاربری"), KeyboardButton("➕ افزایش موجودی")],
        [KeyboardButton("💸 انتقال موجودی"), KeyboardButton("☎️ پشتیبانی")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


def premium_duration_keyboard():
    kb = [
        [InlineKeyboardButton("3 ماه - 1690 تومان (بدون لاگین)", callback_data="premium_3")],
        [InlineKeyboardButton("6 ماه - 2190 تومان (بدون لاگین)", callback_data="premium_6")],
        [InlineKeyboardButton("12 ماه - 3690 تومان (بدون لاگین)", callback_data="premium_12")],
    ]
    return InlineKeyboardMarkup(kb)


def admin_order_keyboard(order_id: str):
    kb = [
        [
            InlineKeyboardButton("✅ تأیید واریز", callback_data=f"admin_approve|{order_id}"),
            InlineKeyboardButton("❌ رد سفارش", callback_data=f"admin_reject|{order_id}"),
        ]
    ]
    return InlineKeyboardMarkup(kb)


# ---------- handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username, user.full_name or "")
    await update.message.reply_text(
        f"به {BOT_NAME} خوش آمدید!\n\n"
        "از منو گزینه مورد نظر را انتخاب کنید.",
        reply_markup=main_menu_keyboard(),
    )
    return CHOOSING_ACTION


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🛍 خرید تلگرام پریمیوم":
        await update.message.reply_text(
            "برای ثبت سفارش پریمیوم یکی از دوره‌ها را انتخاب کنید:",
            reply_markup=premium_duration_keyboard(),
        )
        return CHOOSING_ACTION

    if text == "👤 حساب کاربری":
        user = update.effective_user
        u = data["users"].get(str(user.id), {})
        orders = u.get("orders", [])
        await update.message.reply_text(
            f"اطلاعات شما:\nنام: {u.get('full_name')}\nنام کاربری: @{u.get('username') if u.get('username') else '-'}\n\n"
            f"تعداد سفارش‌ها: {len(orders)}",
            reply_markup=main_menu_keyboard(),
        )
        return CHOOSING_ACTION

    if text == "☎️ پشتیبانی":
        await update.message.reply_text(
            "برای ارتباط با پشتیبانی به ادمین پیام بدهید یا از دکمه‌های پشتیبانی استفاده کنید.\n"
            "اگر سوالی در مورد سفارش داری همینجا بپرس.",
            reply_markup=main_menu_keyboard(),
        )
        return CHOOSING_ACTION

    # سایر دکمه‌ها فعلاً نمایشی هستند
    await update.message.reply_text("این گزینه فعلاً فعال نیست. از منو استفاده کنید.", reply_markup=main_menu_keyboard())
    return CHOOSING_ACTION


async def premium_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data_parts = q.data.split("_")  # e.g. premium_3
    if len(data_parts) == 2 and data_parts[0] == "premium":
        period = data_parts[1]
        user = q.from_user
        # save provisional order
        order_id = f"ord_{len(data['orders']) + 1}"
        order = {
            "id": order_id,
            "user_id": str(user.id),
            "username": user.username,
            "full_name": user.full_name,
            "type": "premium",
            "period_months": int(period),
            "status": "waiting_for_card",  # next: collect card info
            "card_name": None,
            "card_number": None,
        }
        data["orders"][order_id] = order
        # link order to user
        ensure_user(user.id, user.username, user.full_name or "")
        data["users"][str(user.id)]["orders"].append(order_id)
        save_data(data)

        # ask user for card name
        context.user_data["pending_order"] = order_id
        await q.message.reply_text("لطفا نام صاحب کارت را وارد کنید (برای احراز):")
        return COLLECT_CARD_NAME

    await q.message.reply_text("خطا در انتخاب گزینه.")
    return CHOOSING_ACTION


async def collect_card_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    order_id = context.user_data.get("pending_order")
    if not order_id:
        await update.message.reply_text("سفارشی یافت نشد. دوباره از منو شروع کنید.", reply_markup=main_menu_keyboard())
        return CHOOSING_ACTION

    # save name and ask for card number
    data["orders"][order_id]["card_name"] = txt
    save_data(data)
    await update.message.reply_text("حالا شماره کارت (16 یا 19 رقم بدون فاصله) را وارد کنید:")
    return COLLECT_CARD_NUMBER


async def collect_card_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(" ", "")
    order_id = context.user_data.get("pending_order")
    if not order_id:
        await update.message.reply_text("سفارشی یافت نشد. دوباره از منو شروع کنید.", reply_markup=main_menu_keyboard())
        return CHOOSING_ACTION

    # basic validation
    if not txt.isdigit() or len(txt) not in (16, 19):
        await update.message.reply_text("شماره کارت نامعتبر است. لطفا دوباره وارد کنید:")
        return COLLECT_CARD_NUMBER

    data["orders"][order_id]["card_number"] = txt
    data["orders"][order_id]["status"] = "pending_admin"
    save_data(data)

    # notify user
    await update.message.reply_text(
        "اطلاعات شما ثبت شد و برای بررسی به ادمین ارسال شد.\n"
        "پس از تایید ادمین پیام دریافت خواهید کرد.",
        reply_markup=main_menu_keyboard(),
    )

    # notify admin
    order = data["orders"][order_id]
    admin_text = (
        f"🔔 سفارش جدید (نمایشی)\n"
        f"Order ID: {order_id}\n"
        f"کاربر: {order.get('full_name')} / @{order.get('username')}\n"
        f"نوع: پریمیوم — {order.get('period_months')} ماه\n"
        f"نام صاحب کارت: {order.get('card_name')}\n"
        f"شماره کارت: {order.get('card_number')}\n\n"
        "برای تأیید یا رد از دکمه‌های زیر استفاده کنید."
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=admin_order_keyboard(order_id))
    except Exception as e:
        logger.error("خطا در ارسال به ادمین: %s", e)

    context.user_data.pop("pending_order", None)
    return CHOOSING_ACTION


async def admin_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.message.reply_text("فقط ادمین می‌تواند این عملیات را انجام دهد.")
        return

    data_parts = q.data.split("|")
    if len(data_parts) != 2:
        await q.message.reply_text("دادهٔ نامعتبر.")
        return

    action, order_id = data_parts
    order = data["orders"].get(order_id)
    if not order:
        await q.message.reply_text("سفارش یافت نشد.")
        return

    user_chat_id = int(order["user_id"])
    if action == "admin_approve":
        order["status"] = "approved_by_admin"
        save_data(data)
        await q.message.reply_text(f"سفارش {order_id} تأیید شد و کاربر مطلع شد.")
        try:
            await context.bot.send_message(chat_id=user_chat_id, text=(
                f"✅ سفارش شما ({order_id}) توسط ادمین تأیید شد.\n"
                f"شماره کارت شما ثبت و تأیید شد. (این ربات پرداخت واقعی انجام نمی‌دهد — لطفا از طرف ادمین واریز را پیگیری کنید.)"
            ))
        except Exception as e:
            logger.error("خطا در اطلاع‌رسانی کاربر: %s", e)

    elif action == "admin_reject":
        order["status"] = "rejected_by_admin"
        save_data(data)
        await q.message.reply_text(f"سفارش {order_id} رد شد و کاربر مطلع شد.")
        try:
            await context.bot.send_message(chat_id=user_chat_id, text=(
                f"❌ سفارش شما ({order_id}) توسط ادمین رد شد.\n"
                "لطفا در صورت تمایل دوباره اقدام کنید یا با پشتیبانی تماس بگیرید."
            ))
        except Exception as e:
            logger.error("خطا در اطلاع‌رسانی کاربر: %s", e)
    else:
        await q.message.reply_text("عمل نامشخص.")

    return


async def admin_manual_notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # simple admin command to list pending orders
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("شما ادمین نیستید.")
        return
    pending = [o for o in data["orders"].values() if o["status"] == "pending_admin"]
    if not pending:
        await update.message.reply_text("سفارشی در حالت انتظار نیست.")
        return
    txt = "سفارشات در انتظار:\n\n" + "\n\n".join(
        [f"{o['id']} - {o['full_name']} - {o['period_months']} ماه" for o in pending]
    )
    await update.message.reply_text(txt)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("از منو استفاده کنید. /start برای شروع.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)


# ---------- main ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("help", help_command)],
        states={
            CHOOSING_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler),
                CallbackQueryHandler(premium_button_callback, pattern=r"^premium_\d+$"),
                CallbackQueryHandler(admin_action_callback, pattern=r"^admin_(approve|reject)\|"),
            ],
            COLLECT_CARD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_card_name)],
            COLLECT_CARD_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_card_number)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("pending", admin_manual_notify_command))  # admin helper
    app.add_error_handler(error_handler)

    logger.info("Bot started.")
    app.run_polling()


if __name__ == "__main__":
    main()

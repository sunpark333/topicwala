from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from config import SUPER_ADMINS
from storage import GROUP_AUTH, save_data


def is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS


def is_authorized(user_id: int, chat_id: int) -> bool:
    return is_super_admin(user_id) or user_id in GROUP_AUTH.get(chat_id, set())


async def auth_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if not is_super_admin(user.id):
        await update.message.reply_text("❌ Sirf super admin /auth chala sakta hai.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /auth <user_id>")
        return

    target_id = int(context.args[0])
    GROUP_AUTH.setdefault(chat.id, set()).add(target_id)
    save_data()
    await update.message.reply_text(
        f"✅ User `{target_id}` ko auth mil gaya.", parse_mode="Markdown"
    )


async def revokeauth_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if not is_super_admin(user.id):
        await update.message.reply_text("❌ Sirf super admin /revokeauth chala sakta hai.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /revokeauth <user_id>")
        return

    target_id = int(context.args[0])
    GROUP_AUTH.setdefault(chat.id, set()).discard(target_id)
    save_data()
    await update.message.reply_text(
        f"✅ User `{target_id}` ka auth hata diya.", parse_mode="Markdown"
    )


async def whoauth_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    users = GROUP_AUTH.get(chat.id, set())

    if not users:
        await update.message.reply_text("Is group me koi authorized user nahi hai.")
        return

    text = "Authorized users:\n" + "\n".join(
        f"- `{u}`" for u in users
    )

    await update.message.reply_text(text, parse_mode="Markdown")
    await update.message.reply_text(text, parse_mode="Markdown")


def get_auth_handlers():
    return [
        CommandHandler("auth", auth_cmd),
        CommandHandler("revokeauth", revokeauth_cmd),
        CommandHandler("whoauth", whoauth_cmd),
  ]

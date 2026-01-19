import os
import re
import logging
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ---------- logging ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ---------- ENV ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

if not (BOT_TOKEN and MONGO_URI):
    raise RuntimeError("BOT_TOKEN and MONGO_URI required")

# ---------- Mongo ----------
mongo = MongoClient(MONGO_URI)
db = mongo["topic_forward_bot"]

col_config = db["config"]        # {"_id": "config", "source": int, "destination": int}
col_auth = db["auth"]            # {"_id": user_id, "expires_at": datetime}
col_repl = db["replacements"]    # {"_id": old_word, "new": new_word}
col_topics = db["topics"]        # {"_id": dest_chat_id, "mapping": {topic_name: thread_id}}


# ---------- helpers ----------
def now_utc():
    return datetime.now(timezone.utc)


def get_config():
    doc = col_config.find_one({"_id": "config"}) or {}
    return {"source": doc.get("source"), "destination": doc.get("destination")}


def set_config(field, value):
    col_config.update_one({"_id": "config"}, {"$set": {field: value}}, upsert=True)


def add_user(user_id: int, days: int):
    exp = now_utc() + timedelta(days=days)
    col_auth.update_one({"_id": user_id}, {"$set": {"expires_at": exp}}, upsert=True)
    return exp


def is_authorized(user_id: int) -> bool:
    doc = col_auth.find_one({"_id": user_id})
    if not doc:
        return False
    exp = doc.get("expires_at")
    if not isinstance(exp, datetime):
        return False
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return now_utc() < exp


def set_replacement(old: str, new: str):
    col_repl.update_one({"_id": old}, {"$set": {"new": new}}, upsert=True)


def get_replacements():
    return {d["_id"]: d["new"] for d in col_repl.find({})}


def extract_topic(text: str | None):
    if not text:
        return None
    m = re.search(r"Topic:s*(.+)", text, re.IGNORECASE)
    if not m:
        return None
    topic = m.group(1).splitlines()[0].strip()
    return topic or None


def apply_replacements(text: str) -> str:
    repl = get_replacements()
    for o, n in repl.items():
        text = text.replace(o, n)
    return text


async def ensure_auth(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    uid = user.id
    if not is_authorized(uid):
        await update.effective_message.reply_text(
            "❌ Aapko bot ka access nahi hai ya time khatam ho gaya."
        )
        return False
    return True


def get_topic_mapping(dest_chat_id: int) -> dict:
    doc = col_topics.find_one({"_id": dest_chat_id}) or {}
    return doc.get("mapping", {})


def save_topic_mapping(dest_chat_id: int, mapping: dict):
    col_topics.update_one(
        {"_id": dest_chat_id},
        {"$set": {"mapping": mapping}},
        upsert=True,
    )


async def get_or_create_topic_thread(bot, dest_chat_id: int, topic_name: str) -> int:
    """Return message_thread_id for given topic name, create forum topic if needed."""
    topic_name = topic_name[:128]
    mapping = get_topic_mapping(dest_chat_id)

    if topic_name in mapping:
        return mapping[topic_name]

    # create new forum topic (destination chat must be forum-enabled supergroup)
    res = await bot.create_forum_topic(
        chat_id=dest_chat_id,
        name=topic_name,
    )
    thread_id = res.message_thread_id
    mapping[topic_name] = thread_id
    save_topic_mapping(dest_chat_id, mapping)
    log.info(f"Created new topic '{topic_name}' with thread_id {thread_id}")
    return thread_id


# ---------- COMMAND HANDLERS ----------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Hi! Access milne ke baad /status, /setsource, /setdestination, /replace, /sync use karo."
    )


async def adduser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type != "private":
        return
    if len(context.args) != 2:
        await update.effective_message.reply_text("Usage: /adduser <user_id> <days>")
        return

    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("user_id aur days dono integer hone chahiye.")
        return

    exp = add_user(user_id, days)
    await update.effective_message.reply_text(
        f"✅ User {user_id} ko {days} din ka access. Expires: {exp.isoformat()}"
    )


async def setsource_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type != "private":
        return
    if not await ensure_auth(update):
        return

    if len(context.args) != 1:
        await update.effective_message.reply_text("Usage: /setsource <chat_id>")
        return

    try:
        cid = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("chat_id integer hona chahiye.")
        return

    set_config("source", cid)
    await update.effective_message.reply_text(f"✅ Source set: {cid}")


async def setdest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type != "private":
        return
    if not await ensure_auth(update):
        return

    if len(context.args) != 1:
        await update.effective_message.reply_text("Usage: /setdestination <chat_id>")
        return

    try:
        cid = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("chat_id integer hona chahiye.")
        return

    set_config("destination", cid)
    await update.effective_message.reply_text(f"✅ Destination set: {cid}")


async def replace_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type != "private":
        return
    if not await ensure_auth(update):
        return

    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /replace <old> <new text>")
        return

    old = context.args[0]
    new = " ".join(context.args[1:])
    set_replacement(old, new)
    await update.effective_message.reply_text(f"✅ {old} → {new}")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type != "private":
        return
    if not await ensure_auth(update):
        return

    cfg = get_config()
    await update.effective_message.reply_text(
        f"Source: {cfg.get('source')}"
        f"Destination: {cfg.get('destination')}"
    )


async def sync_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type != "private":
        return
    if not await ensure_auth(update):
        return

    if len(context.args) != 2:
        await update.effective_message.reply_text("Usage: /sync <start_id> <end_id>")
        return

    cfg = get_config()
    source = cfg.get("source")
    dest = cfg.get("destination")
    if not (source and dest):
        await update.effective_message.reply_text(
            "❌ Pehle /setsource aur /setdestination set karo."
        )
        return

    try:
        start_id = int(context.args[0])
        end_id = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("start_id aur end_id integer honi chahiye.")
        return

    if start_id > end_id:
        start_id, end_id = end_id, start_id

    bot = context.bot
    await update.effective_message.reply_text(
        f"🔁 Sync {start_id}–{end_id} between {source} → {dest}"
    )

    count = 0
    for mid in range(start_id, end_id + 1):
        try:
            # pehle source se original msg laa lo taaki caption mil jaye
            orig = await bot.forward_message(
                chat_id=update.effective_chat.id,  # temp place (your DM)
                from_chat_id=source,
                message_id=mid,
            )
            caption = orig.caption
            topic_name = extract_topic(caption) or "General"

            # DM me aa gaya, ab turant delete kar do
            try:
                await orig.delete()
            except Exception:
                pass

            thread_id = await get_or_create_topic_thread(bot, dest, topic_name)

            # ab actual destination pe copy, sender hidden + correct thread
            msg = await bot.copy_message(
                chat_id=dest,
                from_chat_id=source,
                message_id=mid,
                message_thread_id=thread_id,
            )

            if msg.caption:
                cap = apply_replacements(msg.caption)
                await bot.edit_message_caption(
                    chat_id=msg.chat_id,
                    message_id=msg.message_id,
                    caption=cap,
                )
            count += 1
        except Exception as e:
            log.warning(f"Sync failed for {mid}: {e}")

    await update.effective_message.reply_text(f"✅ Done. Forwarded approx {count} messages.")


# ---------- main ----------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("adduser", adduser_cmd))
    app.add_handler(CommandHandler("setsource", setsource_cmd))
    app.add_handler(CommandHandler("setdestination", setdest_cmd))
    app.add_handler(CommandHandler("replace", replace_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("sync", sync_cmd))

    log.info("Bot running (auto topics)...")
    app.run_polling()


if __name__ == "__main__":
    main()


            

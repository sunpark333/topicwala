from telegram import Message
from telegram.ext import ContextTypes

from config import DEFAULT_THREAD_ID
from storage import TOPIC_MAP, save_data
from topic_parser import extract_thread_name


async def get_or_create_thread_id(
    context: ContextTypes.DEFAULT_TYPE,
    group_id: int,
    topic_name: str,
) -> int:
    """
    Agar topic_name ka thread id mapping me hai to wahi return.
    Nahi hai to naya forum topic create karke mapping save kar deta hai.
    """
    bot = context.bot
    mapping = TOPIC_MAP.setdefault(group_id, {})

    if topic_name in mapping:
        return mapping[topic_name]

    # naya topic banाओ – bot ko group me admin + topics enabled hona chahiye
    forum_topic = await bot.create_forum_topic(
        chat_id=group_id,
        name=topic_name[:128],  # Telegram limit
    )
    thread_id = forum_topic.message_thread_id
    mapping[topic_name] = thread_id
    save_data()
    return thread_id


async def forward_message_to_group(
    context: ContextTypes.DEFAULT_TYPE,
    group_id: int,
    source_msg: Message,
    thread_id: int,
):
    caption = source_msg.caption or source_msg.text or ""

    if source_msg.video:
        await context.bot.send_video(
            chat_id=group_id,
            video=source_msg.video.file_id,
            caption=caption,
            message_thread_id=thread_id,
        )
    elif source_msg.document:
        await context.bot.send_document(
            chat_id=group_id,
            document=source_msg.document.file_id,
            caption=caption,
            message_thread_id=thread_id,
        )
    else:
        await context.bot.send_message(
            chat_id=group_id,
            text=caption,
            message_thread_id=thread_id,
        )


async def handle_incoming(update, context: ContextTypes.DEFAULT_TYPE):
    """
    Group me aane wali video/doc/text ko handle karega.
    Caption se 'Topic:' nikal ke agar thread nahi hai to naya create karega,
    fir us topic ke thread me message resend karega.
    """
    msg = update.message
    chat_id = msg.chat_id
    user_id = msg.from_user.id

    from auth import is_authorized

    if not is_authorized(user_id, chat_id):
        await msg.reply_text("❌ Aapko is bot ka access nahi hai.")
        return

    caption = msg.caption or msg.text or ""
    topic_name = extract_thread_name(caption)

    if not topic_name:
        # Topic line nahi mili, default thread
        thread_id = DEFAULT_THREAD_ID
    else:
        thread_id = await get_or_create_thread_id(context, chat_id, topic_name)

    await forward_message_to_group(context, chat_id, msg, thread_id)

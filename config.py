import os

BOT_TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"

# yahan apna Telegram user id daalo (super admin)
SUPER_ADMINS = {
    7445620075,  # <-- replace with your user id
}

# agar unknown topic mile to jis thread me bhejna ho (General)
DEFAULT_THREAD_ID = 1

import os

BOT_TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"

# yahan apna Telegram user id daalo (super admin)
SUPER_ADMINS = os.getenv("SUPER_ADMINS")

# agar unknown topic mile to jis thread me bhejna ho (General)
DEFAULT_THREAD_ID = 1

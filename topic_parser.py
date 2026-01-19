import re
from typing import Optional


def extract_thread_name(caption: str) -> Optional[str]:
    """
    Caption me "Topic:" wali line se thread name nikalta hai.

    Example:
      Topic: Notices
    -> "Notices"
    """
    if not caption:
        return None

    match = re.search(r"Topic:s*(.+)", caption, re.IGNORECASE)
    if not match:
        return None

    thread = match.group(1).strip()
    thread = thread.splitlines()[0].strip()
    return thread or None

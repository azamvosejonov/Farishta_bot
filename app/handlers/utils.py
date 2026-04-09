import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

logger = logging.getLogger(__name__)


async def safe_callback_answer(callback: CallbackQuery, *args, **kwargs):
    try:
        return await callback.answer(*args, **kwargs)
    except TelegramBadRequest as exc:
        error_text = str(exc).lower()
        # Can happen after restarts when old callback queries are delivered.
        if "query is too old" in error_text or "query id is invalid" in error_text:
            logger.debug("Ignored expired callback query answer: %s", exc)
            return None
        raise

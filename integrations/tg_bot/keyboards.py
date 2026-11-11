from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from integrations.tg_bot.states import FIELD_LABELS


CALLBACK_PREFIX = "contract"


def review_keyboard(review_id: str, approved: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="✏️ Исправить", callback_data=f"{CALLBACK_PREFIX}:{review_id}:edit")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"{CALLBACK_PREFIX}:{review_id}:cancel")],
    ]
    if approved:
        rows.insert(0, [InlineKeyboardButton(
            text="✅ Сгенерировать и отправить",
            callback_data=f"{CALLBACK_PREFIX}:{review_id}:send",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def field_keyboard(review_id: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=label, callback_data=f"{CALLBACK_PREFIX}:{review_id}:{field}"
        )]
        for field, label in FIELD_LABELS.items()
    ]
    rows.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"{CALLBACK_PREFIX}:{review_id}:cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def document_links(
    drive_url: str | None, signing_url: str | None
) -> InlineKeyboardMarkup | None:
    rows = []
    for title, url in (
        ("📁 Google Drive", drive_url),
        ("✍️ Ссылка на подписание (DocuSign)", signing_url),
    ):
        if url:
            rows.append([InlineKeyboardButton(text=title, url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

import asyncio
import logging
from uuid import uuid4

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message
from pydantic import TypeAdapter, ValidationError

from core.ai_checker import DocumentAIChecker
from core.generator import DocumentGenerator
from core.schemas import ContractInputData, ValidationReport
from integrations.signer import DocuSignService, SignatureRequest
from integrations.storage import GoogleDriveStorage
from integrations.tg_bot.keyboards import (
    CALLBACK_PREFIX,
    document_links,
    field_keyboard,
    review_keyboard,
)
from integrations.tg_bot.parser import ContractParseError, parse_contract_text
from integrations.tg_bot.states import ContractFlow, FIELD_LABELS, field_prompt


logger = logging.getLogger(__name__)
_SIGNER_EMAIL = TypeAdapter(SignatureRequest.model_fields["signer_email"].annotation)
_RISK_LABELS = {
    "low": "🟢 Низкий риск",
    "medium": "🟡 Средний риск",
    "critical": "🔴 Критический риск",
}


def format_report(report: ValidationReport) -> str:
    lines = [_RISK_LABELS[report.risk_level], report.summary]
    for heading, items in (("Ошибки", report.errors), ("Предупреждения", report.warnings)):
        if items:
            lines.extend(["", heading, *(f"• {item}" for item in items)])
    return "\n".join(lines)


async def _answer_long(
    message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    # A 2,000-character chunk fits even when every character takes two UTF-16 units.
    while len(text) > 2000:
        split = text.rfind("\n", 0, 2000)
        split = split if split > 0 else 2000
        await message.answer(text[:split])
        text = text[split:].lstrip("\n")
    await message.answer(text, reply_markup=reply_markup)


async def _review(message: Message, state: FSMContext) -> None:
    values = (await state.get_data())["values"]
    data = {field: values[field] for field in ContractInputData.model_fields}
    await message.answer("Проверяю данные договора…")
    report = await asyncio.to_thread(DocumentAIChecker().check_contract, data)
    approved = report.is_valid and not report.errors and report.risk_level != "critical"
    review_id = uuid4().hex
    await state.update_data(review_id=review_id, approved=approved)
    await state.set_state(ContractFlow.review)
    report_text = format_report(report)
    if approved:
        summary = "\n".join(f"{label}: {values[field]}" for field, label in FIELD_LABELS.items())
        report_text = f"{report_text}\n\nПроверьте данные перед отправкой\n{summary}"
    await _answer_long(message, report_text, review_keyboard(review_id, approved))


async def _ask_next_field(message: Message, state: FSMContext) -> None:
    session = await state.get_data()
    values = session["values"]
    field = next((name for name in FIELD_LABELS if name not in values), None)
    if field is None:
        await _review(message, state)
        return
    await state.update_data(field=field)
    await state.set_state(ContractFlow.field)
    await message.answer(field_prompt(field))


async def start(message: Message) -> None:
    await message.answer(
        "/new_contract — заполнить договор по шагам\n"
        "/quick_contract — извлечь реквизиты из свободного текста\n"
        "/cancel — отменить текущий договор"
    )


async def new_contract(message: Message, state: FSMContext) -> None:
    await state.set_data({"values": {}})
    await _ask_next_field(message, state)


async def quick_contract(message: Message, state: FSMContext) -> None:
    await state.set_data({"values": {}})
    await state.set_state(ContractFlow.quick_text)
    await message.answer("Пришлите одним сообщением известные реквизиты и описание услуг.")


async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Создание договора отменено.")


async def read_quick_text(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Пришлите реквизиты текстовым сообщением.")
        return
    try:
        values = await asyncio.to_thread(parse_contract_text, message.text)
    except ContractParseError as exc:
        await message.answer(str(exc))
        values = {}
    await state.update_data(values=values)
    await _ask_next_field(message, state)


async def read_field(message: Message, state: FSMContext) -> None:
    session = await state.get_data()
    field = session["field"]
    value = (message.text or "").strip()
    if not value:
        await message.answer(field_prompt(field))
        return
    if field == "signer_email":
        try:
            value = _SIGNER_EMAIL.validate_python(value)
        except ValidationError:
            await message.answer("Введите корректный email подписанта, например name@example.org.")
            return

    values = {**session["values"], field: value}
    await state.update_data(values=values)
    await _ask_next_field(message, state)


async def _deliver(message: Message, state: FSMContext, values: dict[str, str]) -> None:
    try:
        contract = ContractInputData.model_validate(values)
        path = await asyncio.to_thread(
            DocumentGenerator().render_docx,
            "contract_template.docx",
            contract.model_dump(),
            f"contract-{uuid4().hex}.docx",
        )
        await message.answer_document(FSInputFile(path, filename="Договор.docx"))
    except Exception as exc:
        logger.error("Ошибка выдачи договора (%s)", type(exc).__name__)
        review_id = uuid4().hex
        await state.update_data(review_id=review_id)
        await message.answer(
            "Не удалось выдать DOCX. Можно повторить попытку.",
            reply_markup=review_keyboard(review_id, approved=True),
        )
        return

    # Consume the confirmation before external calls so a repeat tap cannot send twice.
    await state.clear()
    lines = ["Документ готов"]
    drive_url = None
    signing_url = None
    try:
        upload = await asyncio.to_thread(GoogleDriveStorage().upload_file, path)
        drive_url = upload["web_view_link"]
        if upload["file_id"].startswith("mock-"):
            lines.append("📁 Google Drive — локальная копия, тестовая ссылка.")
    except Exception as exc:
        logger.warning("Ошибка загрузки в Google Drive (%s)", type(exc).__name__)
        lines.append("📁 Google Drive — загрузку не удалось подтвердить.")

    try:
        signature_request = SignatureRequest(
            signer_email=values["signer_email"],
            signer_name=values["signer_name"],
            document_path=path,
            contract_title=f"Договор № {contract.contract_number}",
        )
        signature = await asyncio.to_thread(DocuSignService().send_for_signature, signature_request)
        signing_url = signature.signing_url
        if signature.envelope_id.startswith("mock-"):
            lines.append("✍️ DocuSign — тестовый конверт. Письмо не отправлено.")
        elif signing_url:
            lines.append(f"✍️ DocuSign — конверт {signature.envelope_id}.")
        else:
            lines.append(
                f"✍️ DocuSign — конверт {signature.envelope_id}. "
                "Ссылка на подписание отправлена на email подписанта."
            )
    except Exception as exc:
        logger.warning("Ошибка отправки в DocuSign (%s)", type(exc).__name__)
        lines.append("✍️ DocuSign — отправку не удалось подтвердить.")

    await message.answer("\n".join(lines), reply_markup=document_links(drive_url, signing_url))


async def contract_action(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, payload = (callback.data or "").partition(":")
    review_id, _, action = payload.partition(":")
    session = await state.get_data()
    current_state = await state.get_state()
    message = callback.message
    if (
        not isinstance(message, Message)
        or review_id != session.get("review_id")
        or current_state not in (ContractFlow.review.state, ContractFlow.choose_field.state)
    ):
        await callback.answer("Эта кнопка больше не действует.")
        return

    if action == "cancel":
        await callback.answer()
        await cancel(message, state)
    elif current_state == ContractFlow.review.state and action == "send" and session["approved"]:
        await callback.answer()
        await _deliver(message, state, session["values"])
    elif current_state == ContractFlow.review.state and action == "edit":
        await callback.answer()
        await state.set_state(ContractFlow.choose_field)
        await message.answer("Выберите поле для исправления.", reply_markup=field_keyboard(review_id))
    elif current_state == ContractFlow.choose_field.state and action in FIELD_LABELS:
        await callback.answer()
        await state.update_data(field=action)
        await state.set_state(ContractFlow.field)
        await message.answer(field_prompt(action))
    else:
        await callback.answer("Действие недоступно.")


def create_router() -> Router:
    router = Router(name=__name__)
    router.message.filter(F.chat.type == ChatType.PRIVATE)
    router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)
    router.message.register(start, Command("start"))
    router.message.register(new_contract, Command("new_contract"))
    router.message.register(quick_contract, Command("quick_contract"))
    router.message.register(cancel, Command("cancel"))
    router.message.register(read_quick_text, StateFilter(ContractFlow.quick_text))
    router.message.register(read_field, StateFilter(ContractFlow.field))
    router.callback_query.register(contract_action, F.data.startswith(f"{CALLBACK_PREFIX}:"))
    return router

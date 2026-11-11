import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiogram import Bot
from aiogram.methods import SendDocument, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User

import run_bot
from core.generator import DocumentGenerator
from core.schemas import ContractInputData, ValidationReport
from integrations.signer import LocalSignerMock
from integrations.storage import LocalStorageMock
from integrations.tg_bot import handlers
from integrations.tg_bot.bot import create_dispatcher
from integrations.tg_bot.keyboards import document_links, field_keyboard, review_keyboard
from integrations.tg_bot.parser import parse_contract_text
from integrations.tg_bot.states import FIELD_LABELS
from scripts.create_base_template import create_base_template


@pytest.fixture
def data():
    return {
        "contract_number": "42",
        "contract_date": "11.11.2026",
        "customer_name": "ООО «Вектор»",
        "customer_inn": "7707083893",
        "customer_address": "г. Новосибирск, ул. Примерная, д. 1",
        "executor_name": "ИП Иванов",
        "executor_inn": "540123456723",
        "amount_digits": "150 000 руб.",
        "amount_words": "сто пятьдесят тысяч рублей",
        "service_description": "Разработка Telegram-бота",
    }


def test_parse_contract_text(data):
    raw = (
        "Договор № 42 от 11.11.2026 с ООО «Вектор», ИНН 7707083893, "
        "адрес г. Новосибирск, ул. Примерная, д. 1. Исполнитель ИП Иванов, "
        "ИНН 540123456723. Разработка Telegram-бота за 150 000 руб. "
        "(сто пятьдесят тысяч рублей)."
    )
    client = Mock()
    create = client.chat.completions.create
    create.return_value = SimpleNamespace(choices=[
        SimpleNamespace(
            finish_reason="stop",
            message=SimpleNamespace(content=json.dumps({**data, "unexpected": "ignored"})),
        )
    ])

    parsed = parse_contract_text(raw, client)

    assert ContractInputData.model_validate(parsed).model_dump() == data
    assert parsed == data
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}
    assert create.call_args.kwargs["messages"][1]["content"] == raw


@pytest.mark.parametrize(
    "risk, icon, errors, warnings",
    [
        ("low", "🟢", [], []),
        ("medium", "🟡", [], ["Уточните срок сдачи"]),
        ("critical", "🔴", ["Суммы расходятся"], []),
    ],
)
def test_format_report_and_review_keyboard(risk, icon, errors, warnings):
    report = ValidationReport(
        is_valid=not errors,
        risk_level=risk,
        errors=errors,
        warnings=warnings,
        summary="Проверка завершена",
    )
    text = handlers.format_report(report)
    assert text.startswith(icon)
    assert report.summary in text
    assert all(item in text for item in errors + warnings)
    assert ("Ошибки" in text) == bool(errors)
    assert ("Предупреждения" in text) == bool(warnings)

    keyboard = review_keyboard("test", report.is_valid)
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert buttons[-1].callback_data == "contract:test:cancel"
    assert ("contract:test:send" in [button.callback_data for button in buttons]) == report.is_valid
    assert any(button.callback_data == "contract:test:edit" for button in buttons)


def test_field_and_document_keyboards():
    fields = field_keyboard("a" * 32)
    assert len(fields.inline_keyboard) == len(FIELD_LABELS) + 1
    assert all(
        len(button.callback_data.encode("utf-8")) <= 64
        for row in fields.inline_keyboard for button in row
    )
    drive_url = "https://drive.google.com/example"
    signing_url = "https://docusign.example/sign/abc"
    links = document_links(drive_url, signing_url)
    assert [row[0].url for row in links.inline_keyboard] == [drive_url, signing_url]
    assert len(document_links(drive_url, None).inline_keyboard) == 1
    assert document_links(None, None) is None


@pytest.mark.parametrize("quick", [False, True])
def test_dispatcher_contract_workflow(data, tmp_path, monkeypatch, quick):
    template = create_base_template(tmp_path / "templates" / "contract_template.docx")
    output = tmp_path / "output"
    generator = DocumentGenerator(template.parent, output)
    drive = LocalStorageMock(output / "cloud_storage")
    signer = LocalSignerMock(output / "signature_mock")
    monkeypatch.setattr(handlers, "DocumentGenerator", lambda: generator)
    monkeypatch.setattr(handlers, "GoogleDriveStorage", lambda: drive)
    monkeypatch.setattr(handlers, "DocuSignService", lambda: signer)
    checker = Mock()
    checker.check_contract.side_effect = [
        ValidationReport(
            is_valid=False, risk_level="critical", errors=["Уточните сумму."],
            warnings=[], summary="Есть замечания.",
        ),
        ValidationReport(
            is_valid=True, risk_level="low", errors=[], warnings=[], summary="Договор проверен.",
        ),
    ]
    monkeypatch.setattr(handlers, "DocumentAIChecker", lambda: checker)
    monkeypatch.setattr(handlers, "parse_contract_text", lambda _: {
        field: value for field, value in data.items() if field != "customer_address"
    })
    request = AsyncMock(return_value=True)
    monkeypatch.setattr(Bot, "__call__", request)

    async def exercise():
        dispatcher = create_dispatcher()
        chat = Chat(id=100, type="private")
        user = User(id=100, is_bot=False, first_name="Клиент")
        now = datetime.now(timezone.utc)
        message_id = 0

        async def feed(*, text=None, action=None):
            nonlocal message_id
            message_id += 1
            message = Message(
                message_id=message_id, chat=chat, from_user=user, date=now, text=text
            )
            update = Update(update_id=message_id, message=message)
            if action is not None:
                update = Update(update_id=message_id, callback_query=CallbackQuery(
                    id=str(message_id), from_user=user, chat_instance="chat",
                    message=message, data=action,
                ))
            await dispatcher.feed_update(bot, update)

        def latest_message():
            return next(
                call.args[0] for call in reversed(request.call_args_list)
                if isinstance(call.args[0], SendMessage)
            )

        async with Bot("123456:test") as bot:
            if quick:
                await feed(text="/quick_contract")
                await feed(text="Свободный текст договора")
                assert latest_message().text.startswith("Адрес заказчика")
                await feed(text=data["customer_address"])
            else:
                await feed(text="/new_contract")
                for field in FIELD_LABELS:
                    if field in data:
                        await feed(text=data[field])

            await feed(text="Иван Петров")
            await feed(text="invalid-email")
            assert "корректный email" in latest_message().text
            await feed(text="signer@example.org")
            assert "Уточните сумму" in latest_message().text
            blocked = latest_message().reply_markup.inline_keyboard[0][0].callback_data
            await feed(action=blocked.replace(":edit", ":send"))
            assert not output.exists()

            await feed(action=blocked)
            edit = next(
                row[0].callback_data for row in latest_message().reply_markup.inline_keyboard
                if row[0].callback_data.endswith(":amount_digits")
            )
            await feed(action=edit)
            await feed(text=data["amount_digits"])
            approved = latest_message().reply_markup.inline_keyboard[0][0].callback_data
            assert "signer@example.org" in latest_message().text

            await feed(action=approved)
            card = latest_message()
            assert "тестовый конверт" in card.text
            assert len(card.reply_markup.inline_keyboard) == 2
            await feed(action=approved)

        assert [
            call.args[0].document.filename for call in request.call_args_list
            if isinstance(call.args[0], SendDocument)
        ] == ["Договор.docx"]

    asyncio.run(exercise())
    assert checker.check_contract.call_count == 2
    assert len(list(drive.storage_dir.glob("*.docx"))) == 1
    assert len(list(signer.storage_dir.iterdir())) == 1


def test_run_bot_without_token(monkeypatch, capsys):
    monkeypatch.setattr(run_bot, "settings", SimpleNamespace(telegram_bot_token=" "))
    assert run_bot.main() == 0
    assert "TELEGRAM_BOT_TOKEN не задан" in capsys.readouterr().out

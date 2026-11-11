import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from openai import APIConnectionError

from core.ai_checker import DocumentAIChecker
from core.generator import DocumentGenerator, extract_text_from_docx
from scripts.create_base_template import create_base_template


@pytest.fixture
def contract_data():
    return {
        "contract_number": "42",
        "contract_date": "29 февраля 2024 г.",
        "customer_name": "ООО «Заказчик»",
        "customer_inn": "5401234566",
        "customer_address": "г. Новосибирск, ул. Примерная, д. 1",
        "executor_name": "ИП Демонстрационный Исполнитель",
        "executor_inn": "540123456723",
        "service_description": "Подготовить отчёт об анализе анкет.",
        "amount_digits": "50 000 руб.",
        "amount_words": "пятьдесят тысяч рублей 00 копеек",
    }


def completion(is_valid, risk_level, errors):
    content = json.dumps(
        {
            "is_valid": is_valid,
            "risk_level": risk_level,
            "errors": errors,
            "warnings": [],
            "summary": "Проверка завершена.",
        }
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))]
    )


def test_check_contract_valid(contract_data, tmp_path):
    template = create_base_template(tmp_path / "templates" / "contract_template.docx")
    generator = DocumentGenerator(template.parent, tmp_path / "output")
    path = generator.render_docx(template.name, contract_data, "contract.docx")
    text = extract_text_from_docx(path)
    assert contract_data["service_description"] in text
    assert contract_data["customer_address"] in text
    assert text.index("1. Предмет договора") < text.index(contract_data["customer_address"])

    client = Mock()
    create = client.chat.completions.create
    create.return_value = completion(True, "low", [])

    report = DocumentAIChecker(client).check_contract(contract_data, text)

    assert report.is_valid is True
    assert report.risk_level == "low"
    create.assert_called_once()
    request = create.call_args.kwargs
    assert request["response_format"] == {"type": "json_object"}
    assert json.loads(request["messages"][1]["content"]) == {
        "data": contract_data,
        "contract_text": text,
    }


def test_check_contract_amount_mismatch(contract_data):
    contract_data["amount_digits"] = "100 000 руб."
    client = Mock()
    error = "Сумма цифрами не совпадает с суммой прописью."
    client.chat.completions.create.return_value = completion(False, "critical", [error])

    report = DocumentAIChecker(client).check_contract(contract_data)

    assert report.is_valid is False
    assert report.risk_level == "critical"
    assert error in report.errors


@pytest.mark.parametrize("field, value", [
    ("customer_inn", "5401234567"),
    ("executor_inn", "540123456724"),
    ("contract_date", "29.02.2026"),
])
def test_check_contract_rejects_invalid_input_locally(contract_data, field, value):
    contract_data[field] = value
    client = Mock()

    report = DocumentAIChecker(client).check_contract(contract_data)

    assert report.is_valid is False
    assert report.risk_level == "critical"
    assert any(error.startswith(field) for error in report.errors)
    client.chat.completions.create.assert_not_called()


def test_check_contract_falls_back_on_api_connection_error(contract_data):
    client = Mock()
    client.chat.completions.create.side_effect = APIConnectionError(
        request=Mock()
    )

    report = DocumentAIChecker(client).check_contract(contract_data)

    assert report.is_valid is True
    assert report.risk_level == "medium"
    assert not report.errors
    assert any("AI-проверка недоступна" in warning for warning in report.warnings)

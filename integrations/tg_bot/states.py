from aiogram.fsm.state import State, StatesGroup


class ContractFlow(StatesGroup):
    quick_text = State()
    field = State()
    review = State()
    choose_field = State()


FIELD_LABELS = {
    "contract_number": "Номер договора",
    "contract_date": "Дата договора",
    "customer_name": "Наименование заказчика",
    "customer_inn": "ИНН заказчика",
    "customer_address": "Адрес заказчика",
    "executor_name": "Наименование исполнителя",
    "executor_inn": "ИНН исполнителя",
    "amount_digits": "Сумма цифрами",
    "amount_words": "Сумма прописью",
    "service_description": "Описание услуг",
    "signer_name": "Имя подписанта",
    "signer_email": "Email подписанта",
}

_FIELD_EXAMPLES = {
    "contract_date": "ДД.ММ.ГГГГ",
    "amount_digits": "50 000 руб.",
    "amount_words": "пятьдесят тысяч рублей 00 копеек",
}


def field_prompt(field: str) -> str:
    example = _FIELD_EXAMPLES.get(field)
    suffix = f" (например, {example})" if example else ""
    return f"{FIELD_LABELS[field]}{suffix}. Введите значение."

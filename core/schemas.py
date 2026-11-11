import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


_RUSSIAN_MONTHS = {
    name: number
    for number, name in enumerate(
        "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split(),
        start=1,
    )
}
_INN_WEIGHTS = {
    10: ((2, 4, 10, 3, 5, 9, 4, 6, 8),),
    12: ((7, 2, 4, 10, 3, 5, 9, 4, 6, 8), (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)),
}


class ContractInputData(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)

    contract_number: str
    contract_date: str
    customer_name: str
    customer_inn: str
    customer_address: str
    executor_name: str
    executor_inn: str
    service_description: str
    amount_digits: str
    amount_words: str

    @field_validator("customer_inn", "executor_inn")
    @classmethod
    def validate_inn(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9]{10}|[0-9]{12}", value):
            raise ValueError("ИНН должен содержать 10 или 12 цифр")
        digits = list(map(int, value))
        if not any(digits):
            raise ValueError("ИНН не может состоять из нулей")
        for weights in _INN_WEIGHTS[len(digits)]:
            checksum = sum(digit * weight for digit, weight in zip(digits, weights)) % 11 % 10
            if checksum != digits[len(weights)]:
                raise ValueError("Неверная контрольная цифра ИНН")
        return value

    @field_validator("contract_date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        iso = re.fullmatch(r"([0-9]{4})-([0-9]{2})-([0-9]{2})", value)
        dotted = re.fullmatch(r"([0-9]{2})\.([0-9]{2})\.([0-9]{4})", value)
        written = re.fullmatch(r"([0-9]{1,2})\s+([а-я]+)\s+([0-9]{4})(?:\s+г\.?)?", value.lower())
        try:
            if iso:
                date(*map(int, iso.groups()))
            elif dotted:
                day, month, year = map(int, dotted.groups())
                date(year, month, day)
            elif written:
                day, month_name, year = written.groups()
                date(int(year), _RUSSIAN_MONTHS.get(month_name, 0), int(day))
            else:
                raise ValueError
        except ValueError:
            raise ValueError(
                "Укажите календарную дату в формате ДД.ММ.ГГГГ, ГГГГ-ММ-ДД или «11 ноября 2026 г.»"
            ) from None
        return value


class ValidationReport(BaseModel):
    model_config = ConfigDict(strict=True, str_strip_whitespace=True, str_min_length=1)

    is_valid: bool
    risk_level: Literal["low", "medium", "critical"]
    errors: list[str]
    warnings: list[str]
    summary: str

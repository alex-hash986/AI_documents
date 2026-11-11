from core.ai_checker import DocumentAIChecker
from core.generator import DocumentGenerator
from core.schemas import ValidationReport


_RISK_LABELS = {"low": "низкий", "medium": "средний", "critical": "критический"}


def print_report(report: ValidationReport) -> None:
    print("\nПроверка договора")
    print("─" * 36)
    print(f"Уровень риска: {_RISK_LABELS[report.risk_level]}")
    print(report.summary)
    for heading, items in (("Ошибки", report.errors), ("Рекомендации", report.warnings)):
        if items:
            print(f"\n{heading}")
            for item in items:
                print(f"  • {item}")


def main() -> int:
    data = {
        "contract_number": "ДЕМО-001",
        "contract_date": "11.11.2026",
        "customer_name": "ООО «Демо-заказчик»",
        "customer_inn": "5401234566",
        "customer_address": "г. Новосибирск, ул. Примерная, д. 1",
        "executor_name": "ИП Демонстрационный Исполнитель",
        "executor_inn": "540123456723",
        "service_description": (
            "Подготовить один письменный отчёт о результатах анализа 100 анкет "
            "и передать его заказчику в формате PDF до 30.11.2026."
        ),
        "amount_digits": "50 000 руб.",
        "amount_words": "пятьдесят тысяч рублей 00 копеек",
    }
    report = DocumentAIChecker().check_contract(data)
    print_report(report)
    if not report.is_valid:
        print("\nГенерация договора заблокирована.")
        return 1

    path = DocumentGenerator().render_docx(
        "contract_template.docx", data, "demo_contract.docx"
    )
    print(f"\nДоговор сохранён: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

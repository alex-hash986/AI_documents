from pathlib import Path

from docx import Document
from docx.document import Document as WordDocument
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


DESTINATION = (
    Path(__file__).resolve().parents[1]
    / "ТЗ_Система_автоматизации_документооборота_с_AI.docx"
)
TITLE = (
    "Техническое задание: Интеллектуальная система автоматизации "
    "документооборота с AI-верификацией и цифровым подписанием "
    "(AI DocFlow & Verification System)"
)

REQUIREMENTS = (
    (
        "4.1 Динамические шаблоны",
        "Система должна хранить библиотеку DOCX-шаблонов договоров, счетов и актов. "
        "Шаблоны должны поддерживать поля, условия и циклы Jinja2 для подстановки "
        "реквизитов и формирования повторяющихся строк.",
    ),
    (
        "4.2 Извлечение реквизитов",
        "LLM должен преобразовывать свободный текст из чата Telegram в структурированные "
        "реквизиты документа. Если данных недостаточно, бот запрашивает недостающие поля "
        "у оператора.",
    ),
    (
        "4.3 Двухуровневая AI-верификация",
        "На первом уровне система проверяет обязательные поля, формат даты и контрольные "
        "цифры ИНН детерминированными правилами Python. На втором уровне LLM сверяет суммы "
        "цифрами и прописью и проводит семантический аудит условий договора, включая признаки "
        "трудовых отношений. Отчёт разделяет блокирующие ошибки и предупреждения.",
    ),
    (
        "4.4 Экспорт",
        "Система должна формировать редактируемый DOCX и экспортировать документ в PDF. "
        "При недоступности PDF-конвертера оператор получает DOCX и уведомление о сбое.",
    ),
    (
        "4.5 Облачное хранение",
        "Система должна загружать документы через Google Drive API и предоставлять публичную "
        "ссылку с доступом на чтение всем, у кого она есть.",
    ),
    (
        "4.6 Электронная подпись",
        "Система должна создавать конверт через DocuSign API и отправлять приглашение "
        "подписанту. Изменения статуса конверта должны поступать через асинхронные уведомления "
        "DocuSign Connect. Для демонстраций предусмотрен mock-режим с тестовыми конвертами "
        "и ссылками.",
    ),
    (
        "4.7 Мобильный интерфейс оператора",
        "Telegram-бот на aiogram 3.x должен поддерживать быстрый разбор текста и пошаговый "
        "ввод через FSM. Оператор должен получать отчёт, исправлять выбранное поле через "
        "инлайн-кнопки и подтверждать генерацию и отправку документа на подпись.",
    ),
)

RISKS = (
    (
        "Недоступность LLM API и облаков",
        "Локальный fallback-режим, офлайн-валидаторы Pydantic и локальное хранилище. "
        "Система сообщает оператору, если AI-проверка или облачная операция недоступна.",
    ),
    (
        "Галлюцинации LLM",
        "Строгая JSON-схема ответа, temperature=0.1 для поддерживающих параметр моделей "
        "и обязательная проверка контрольных цифр ИНН в Python.",
    ),
    (
        "Бюджет и лимиты API",
        "Поддержка легковесных быстрых моделей, кэширование повторных запросов "
        "и mock-адаптеры для тестов и демонстраций.",
    ),
    (
        "Защита персональных данных",
        "Исключение чувствительных данных из открытых логов. Для демонстраций используются "
        "обезличенные реквизиты и сущности.",
    ),
)

COMPONENTS = (
    ("Python 3.10+", "Выполнение бизнес-логики и интеграций"),
    ("docxtpl", "Рендеринг динамических DOCX-шаблонов с Jinja2"),
    ("pydantic", "Схемы реквизитов и отчёта, локальная валидация"),
    ("openai", "Вызовы LLM для извлечения реквизитов и аудита"),
    ("aiogram 3.x", "Telegram-интерфейс, FSM и инлайн-кнопки"),
    ("google-api-python-client", "Клиент Google Drive API v3"),
    ("docusign-esign", "Конверты DocuSign и статусы подписания"),
    ("pytest", "Модульные и интеграционные тесты с моками"),
)


def configure_layout(document: WordDocument) -> None:
    section = document.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin = section.right_margin = Cm(2.2)
    section.top_margin = section.bottom_margin = Cm(2)
    section.footer_distance = Cm(0.95)

    for name, size in (
        ("Normal", 11), ("Title", 23), ("Heading 1", 16),
        ("Heading 2", 12), ("Footer", 9),
    ):
        style = document.styles[name]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.bold = name in {"Title", "Heading 1", "Heading 2"}
        style.font.italic = False
        fonts = style.element.get_or_add_rPr().rFonts
        for attribute in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
            fonts.attrib.pop(qn(f"w:{attribute}"), None)
        for attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
            fonts.set(qn(f"w:{attribute}"), "Arial")

    normal = document.styles["Normal"].paragraph_format
    normal.space_after = Pt(7)
    normal.line_spacing = 1.15

    title_style = document.styles["Title"]
    title_style.paragraph_format.space_after = Pt(16)
    title_style.paragraph_format.line_spacing = 1.1
    title_style.paragraph_format.keep_with_next = True
    for border in title_style.element.xpath("./w:pPr/w:pBdr"):
        border.getparent().remove(border)

    for name, before, after in (("Heading 1", 14, 6), ("Heading 2", 9, 3)):
        fmt = document.styles[name].paragraph_format
        fmt.space_before = Pt(before)
        fmt.space_after = Pt(after)
        fmt.keep_with_next = True

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    page = OxmlElement("w:fldSimple")
    page.set(qn("w:instr"), "PAGE")
    footer._p.append(page)


def add_table(
    document: WordDocument,
    headings: tuple[str, str],
    data: tuple[tuple[str, str], ...],
    widths: tuple[float, float],
) -> None:
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    table.autofit = False
    for column, width in zip(table.columns, widths):
        column.width = Cm(width)

    props = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = OxmlElement(f"w:{edge}")
        for key, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
            border.set(qn(f"w:{key}"), value)
        borders.append(border)
    props.insert_element_before(borders, "w:tblLayout")
    margins = OxmlElement("w:tblCellMar")
    for edge, value in (("top", "85"), ("bottom", "85"), ("left", "125"), ("right", "125")):
        margin = OxmlElement(f"w:{edge}")
        margin.set(qn("w:w"), value)
        margin.set(qn("w:type"), "dxa")
        margins.append(margin)
    props.insert_element_before(margins, "w:tblLook")

    for index, row_values in enumerate((headings, *data)):
        row = table.add_row()
        row_props = row._tr.get_or_add_trPr()
        row_props.append(OxmlElement("w:cantSplit"))
        if index == 0:
            row_props.append(OxmlElement("w:tblHeader"))
        for cell, text, width in zip(row.cells, row_values, widths):
            cell.width = Cm(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.08
            paragraph.paragraph_format.keep_with_next = index == 0
            run = paragraph.add_run(text)
            run.font.size = Pt(10.5)
            if index == 0:
                run.bold = True
                shading = OxmlElement("w:shd")
                shading.set(qn("w:fill"), "E7EBF0")
                cell._tc.get_or_add_tcPr().append(shading)


def generate_document(destination: Path = DESTINATION) -> Path:
    document = Document()
    document.core_properties.title = TITLE
    document.core_properties.subject = "Техническое задание, версия 1.0"
    document.core_properties.author = ""
    configure_layout(document)

    title, project_name = TITLE.rsplit(" (", 1)
    heading = document.add_paragraph(title, style="Title")
    heading.add_run(f"\n({project_name}").font.size = Pt(15)
    add_table(
        document,
        ("Параметр", "Значение"),
        (("Версия", "1.0"), ("Статус", "Утверждено"), ("Дата", "Ноябрь 2026")),
        (4.3, 12.3),
    )

    document.add_heading("1 Описание проекта и предпосылки разработки", level=1)
    document.add_paragraph(
        "В малом и среднем бизнесе (SMB) и секторе B2B-услуг договоры, счета и акты "
        "часто формируют вручную на основе прошлых документов. Сотрудники переносят "
        "реквизиты, сверяют суммы и пересылают версии на согласование. Исправление "
        "ошибок повторяет часть цикла и откладывает подписание."
    )
    document.add_heading("2 Цель проекта", level=1)
    document.add_paragraph(
        "Сократить цикл создания документа с 35–40 минут до 1,5 минуты и исключить "
        "человеческий фактор при проверке реквизитов за счёт автоматической валидации. "
        "Целевое время измеряется от ввода исходных данных до получения проверенного "
        "файла, готового к отправке на подпись."
    )
    document.add_heading("3 Целевая аудитория и её задачи", level=1)
    document.add_paragraph(
        "Система предназначена для B2B-компаний и отделов продаж, самозанятых "
        "и фрилансеров, юридических и консалтинговых агентств."
    )
    document.add_paragraph(
        "Эти пользователи регулярно копируют реквизиты вручную, исправляют опечатки в ИНН "
        "и расхождения сумм цифрами и прописью. При подготовке договоров ГПХ требуется "
        "выявлять риск их переквалификации в трудовые договоры. Задержки согласования "
        "и пересылки документов удлиняют сроки подписания."
    )

    heading = document.add_heading("4 Функциональные требования", level=1)
    heading.paragraph_format.page_break_before = True
    for title, requirement in REQUIREMENTS:
        document.add_heading(title, level=2)
        document.add_paragraph(requirement)

    heading = document.add_heading("5 Ограничения и риски проекта", level=1)
    heading.paragraph_format.page_break_before = True
    add_table(document, ("Риск или ограничение", "Мера снижения"), RISKS, (5.1, 11.5))

    document.add_heading("6 Архитектура и стек технологий", level=1)
    document.add_paragraph(
        "Telegram-бот передаёт реквизиты модулю верификации. После подтверждения "
        "генератор формирует файл, а адаптеры выполняют загрузку и отправку на подпись."
    )
    add_table(document, ("Компонент", "Назначение"), COMPONENTS, (5.7, 10.9))

    destination.parent.mkdir(parents=True, exist_ok=True)
    document.save(destination)
    return destination


if __name__ == "__main__":
    print(generate_document())

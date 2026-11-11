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
    / "Бизнес_кейс_AI_DocFlow_Выгоды_и_расчет_ROI.docx"
)
TITLE = (
    "Бизнес-кейс: Интеллектуальная система автоматизации документооборота "
    "с AI-верификацией (AI DocFlow)"
)
SUBTITLE = "Обоснование экономической эффективности, расчет окупаемости (ROI) и коммерческие выгоды"


def configure_layout(document: WordDocument) -> None:
    section = document.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin = section.right_margin = Cm(2.1)
    section.top_margin = section.bottom_margin = Cm(1.8)
    section.footer_distance = Cm(0.85)

    for name, size in (
        ("Normal", 10.5), ("Title", 21), ("Subtitle", 12), ("Heading 1", 14), ("Footer", 9)
    ):
        style = document.styles[name]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.bold = name in {"Title", "Heading 1"}
        style.font.italic = False
        fonts = style.element.get_or_add_rPr().rFonts
        for attribute in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
            fonts.attrib.pop(qn(f"w:{attribute}"), None)
        for attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
            fonts.set(qn(f"w:{attribute}"), "Arial")
        style.paragraph_format.line_spacing = 1.12
        style.paragraph_format.space_after = Pt(5)

    for name in ("Title", "Subtitle", "Heading 1"):
        style = document.styles[name]
        style.paragraph_format.keep_with_next = True
        for border in style.element.xpath("./w:pPr/w:pBdr"):
            border.getparent().remove(border)
    document.styles["Heading 1"].paragraph_format.space_before = Pt(11)
    document.styles["Subtitle"].paragraph_format.space_after = Pt(10)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)


def add_table(
    document: WordDocument, rows: tuple[tuple[str, ...], ...], widths: tuple[float, ...]
) -> None:
    table = document.add_table(rows=0, cols=len(widths))
    table.style = "Table Grid"
    table.autofit = False
    for column, width in zip(table.columns, widths):
        column.width = Cm(width)

    props = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        edge = OxmlElement(f"w:{side}")
        for key, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
            edge.set(qn(f"w:{key}"), value)
        borders.append(edge)
    props.insert_element_before(borders, "w:tblLayout")
    margins = OxmlElement("w:tblCellMar")
    for side, width in (("top", "65"), ("bottom", "65"), ("left", "120"), ("right", "120")):
        edge = OxmlElement(f"w:{side}")
        edge.set(qn("w:w"), width)
        edge.set(qn("w:type"), "dxa")
        margins.append(edge)
    props.insert_element_before(margins, "w:tblLook")

    for index, values in enumerate(rows):
        row = table.add_row()
        row_props = row._tr.get_or_add_trPr()
        row_props.append(OxmlElement("w:cantSplit"))
        if index == 0:
            row_props.append(OxmlElement("w:tblHeader"))
        for cell, value, width in zip(row.cells, values, widths):
            cell.width = Cm(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.keep_with_next = index == 0
            run = paragraph.add_run(value)
            if index == 0:
                run.bold = True
                run.font.color.rgb = RGBColor.from_string("FFFFFF")
            shading = OxmlElement("w:shd")
            shading.set(qn("w:fill"), "203A57" if index == 0 else ("F3F6F9" if index % 2 == 0 else "FFFFFF"))
            cell._tc.get_or_add_tcPr().append(shading)


def generate_document(destination: Path = DESTINATION) -> Path:
    document = Document()
    document.core_properties.title = TITLE
    document.core_properties.subject = SUBTITLE
    document.core_properties.author = ""
    configure_layout(document)

    document.add_paragraph(TITLE, style="Title")
    document.add_paragraph(SUBTITLE, style="Subtitle")
    document.add_heading("1 Карточка решения", level=1)
    add_table(document, (
        ("Параметр", "Описание"),
        ("Сегмент рынка", "B2B-услуги, IT и аутсорсинг, консалтинг, отделы продаж малого и среднего бизнеса."),
        ("Назначение", "Создание договоров и актов из свободного текста, двухуровневая проверка рисков, интеграция с Google Drive и DocuSign."),
        ("Стек", "Python 3.10+, OpenAI API, Pydantic, aiogram 3.x, docxtpl, Google Drive API, DocuSign API."),
    ), (3.6, 13.2))

    document.add_heading("2 Проблематика клиента до внедрения", level=1)
    document.add_paragraph(
        "На ручной перенос реквизитов и согласование одного документа уходит 35–40 минут. "
        "В исходном сценарии до 7% документов содержат ошибки, включая некорректные ИНН "
        "и расхождения сумм цифрами и прописью."
    )
    document.add_paragraph(
        "Признаки трудовых отношений в договорах ГПХ создают риск претензий и штрафов. "
        "Из-за долгого согласования и подписания сделки могут задерживаться на 3–5 дней."
    )

    document.add_heading("3 Операционные показатели", level=1)
    document.add_paragraph("Базовые значения и цели для пилотного внедрения.")
    add_table(document, (
        ("Показатель", "До", "После, цель"),
        ("Время подготовки документа", "35–40 минут", "45–60 секунд, примерно в 40 раз быстрее"),
        ("Ошибки в контрольных цифрах ИНН", "3–5%", "0% в пилотной выборке, проверка Pydantic"),
        ("Расхождения сумм цифрами и прописью", "До 7%", "0% в пилотной выборке, проверка LLM"),
        ("Запуск отправки на подпись", "1–3 часа", "Одно нажатие после проверки"),
        ("Доступность резервного сценария", "Зависит от ручной обработки", "Цель 100% в тестах отказа облака с локальными и mock-адаптерами"),
    ), (5.6, 3.7, 7.5))
    note = document.add_paragraph(
        "В резервном режиме продолжается локальная обработка. Фактическая отправка "
        "на подпись требует доступа к DocuSign."
    )
    note.paragraph_format.space_before = Pt(7)

    heading = document.add_heading("4 Финансовая модель и расчёт ROI", level=1)
    heading.paragraph_format.page_break_before = True
    document.add_paragraph(
        "Расчётный сценарий для отдела продаж из пяти менеджеров при объёме "
        "300 документов в месяц. Месячная ставка менеджера составляет 90 000 руб., "
        "округлённая расчётная ставка — 560 руб. в час."
    )
    add_table(document, (
        ("Показатель", "Расчёт и результат"),
        ("Ручной документооборот", "300 × 35 мин = 175 ч в месяц. При округлённой ставке это около 98 000 руб. Ориентир бизнес-кейса — 97 500 руб. в месяц."),
        ("Работа с AI DocFlow", "300 × 45 сек = 3,75 ч в месяц на весь отдел. Стоимость времени — около 2 100 руб."),
        ("Экономия рабочего времени", "175 − 3,75 = 171,25 ч в месяц. Около 170 часов можно направить на продажи."),
        ("Экономия в эквиваленте ФОТ", "97 500 − 2 100 = 95 400 руб. в месяц, или около 95 000 руб."),
        ("AI API и хостинг", "Менее 1 000 руб. в месяц по допущению модели."),
        ("Месячный эффект после расходов", "Около 94 400 руб. при расчёте по верхней границе расходов."),
        ("Внедрение под ключ", "120 000–180 000 руб., разовые инвестиции."),
        ("Срок окупаемости", "120 000–180 000 ÷ 94 400 ≈ 1,3–1,9 месяца. Плановый ориентир — 1,5–2 месяца."),
        ("ROI за 12 месяцев", "Около 529–844% при стабильном эффекте. Формула: (94 400 × 12 − инвестиции) ÷ инвестиции × 100%."),
    ), (6.1, 10.7))
    note = document.add_paragraph(
        "Экономия отражает стоимость высвобождённого времени. Модель учитывает AI API "
        "и хостинг. Лицензии внешних сервисов оцениваются отдельно."
    )
    note.paragraph_format.space_before = Pt(8)

    document.add_heading("5 Преимущества для бизнеса и состав поставки", level=1)
    document.add_paragraph(
        "Менеджеры могут готовить документы со смартфона в Telegram. Проверка ИНН, "
        "сумм и формулировок снижает риск замечаний бухгалтерии и претензий при проверках."
    )
    document.add_paragraph(
        "В поставку входят настроенный Telegram-бот, комплект Jinja2-шаблонов, "
        "настройка облачного хранилища, модуль электронной подписи и документация."
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    document.save(destination)
    return destination


if __name__ == "__main__":
    print(generate_document())

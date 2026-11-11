from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt


TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "contract_template.docx"


def create_base_template(destination: Path = TEMPLATE_PATH) -> Path:
    document = Document()
    document.core_properties.title = "Договор возмездного оказания услуг"
    section = document.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = section.right_margin = Cm(2.5)
    section.top_margin = section.bottom_margin = Cm(2)

    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.space_after = Pt(8)
    for name, size in (("Title", 16), ("Heading 1", 13)):
        style = document.styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True

    title = document.add_paragraph(
        "Договор возмездного оказания услуг № {{ contract_number }}", style="Title"
    )
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date = document.add_paragraph("{{ contract_date }}")
    date.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    document.add_paragraph(
        "{{ customer_name }}, ИНН {{ customer_inn }}, далее — «Заказчик», "
        "и {{ executor_name }}, ИНН {{ executor_inn }}, далее — «Исполнитель», "
        "совместно именуемые «Стороны», заключили настоящий договор о нижеследующем."
    )
    document.add_heading("1. Предмет договора", level=1)
    document.add_paragraph(
        "1.1. Исполнитель обязуется по заданию Заказчика оказать следующие услуги, "
        "а Заказчик обязуется принять и оплатить их:"
    )
    document.add_paragraph("{{ service_description }}")
    document.add_paragraph(
        "1.2. Стороны согласовывают сроки оказания услуг в письменной форме."
    )
    document.add_heading("2. Стоимость услуг и порядок оплаты", level=1)
    document.add_paragraph(
        "2.1. Стоимость услуг составляет {{ amount_digits }} ({{ amount_words }})."
    )
    document.add_paragraph(
        "2.2. Заказчик оплачивает услуги в течение пяти рабочих дней со дня "
        "подписания Сторонами акта оказанных услуг."
    )
    document.add_heading("3. Реквизиты и подписи сторон", level=1)
    table = document.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    customer, executor = table.rows[0].cells
    for cell, label, lines in (
        (customer, "Заказчик", (
            "{{ customer_name }}", "ИНН {{ customer_inn }}", "{{ customer_address }}"
        )),
        (executor, "Исполнитель", ("{{ executor_name }}", "ИНН {{ executor_inn }}")),
    ):
        cell.paragraphs[0].add_run(label).bold = True
        for line in lines:
            cell.add_paragraph(line)
        cell.add_paragraph("Подпись: __________________")

    destination.parent.mkdir(parents=True, exist_ok=True)
    document.save(destination)
    return destination


if __name__ == "__main__":
    print(create_base_template())

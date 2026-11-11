from pathlib import Path

from docx import Document

from core.generator import DocumentGenerator
from scripts.create_base_template import create_base_template


def test_render_docx_fills_contract(tmp_path):
    templates_dir = tmp_path / "templates"
    output_dir = tmp_path / "output"
    template = create_base_template(templates_dir / "contract_template.docx")
    generator = DocumentGenerator(templates_dir, output_dir)
    context = {
        "contract_number": "42/2026",
        "contract_date": "11 ноября 2026 г.",
        "customer_name": "ООО «Альфа & Бета»",
        "customer_inn": "5401234567",
        "customer_address": "г. Новосибирск, ул. Советская, д. 1",
        "executor_name": "ИП Иванов Иван Иванович",
        "executor_inn": "540123456789",
        "service_description": "Подготовка отчёта <по результатам аудита>",
        "amount_digits": "25 000 руб.",
        "amount_words": "двадцать пять тысяч рублей",
    }

    result = generator.render_docx(template.name, context, "contract.docx")

    assert Path(result) == output_dir / "contract.docx"
    document = Document(result)
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    paragraphs.extend(cell.text for row in document.tables[0].rows for cell in row.cells)
    rendered = "\n".join(paragraphs)
    for value in context.values():
        assert value in rendered
    assert "{{" not in rendered


def test_convert_to_pdf_returns_none_when_libreoffice_is_missing(
    tmp_path, monkeypatch, caplog
):
    source = create_base_template(tmp_path / "contract.docx")
    monkeypatch.setattr("core.generator.platform.system", lambda: "Linux")
    monkeypatch.setattr("core.generator.shutil.which", lambda name: None)

    assert DocumentGenerator().convert_to_pdf(str(source)) is None
    assert "LibreOffice не найден в PATH" in caplog.text
    assert not source.with_suffix(".pdf").exists()

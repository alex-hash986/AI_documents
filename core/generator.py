import logging
import platform
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from docx.text.paragraph import Paragraph
from docxtpl import DocxTemplate

from config import settings


logger = logging.getLogger(__name__)


def extract_text_from_docx(docx_path: str) -> str:
    document = Document(docx_path)
    return "\n".join(_block_text(document))


def _block_text(container):
    for block in container.iter_inner_content():
        if isinstance(block, Paragraph):
            if block.text.strip():
                yield block.text
        else:
            for row in block.rows:
                for cell in row.cells:
                    yield from _block_text(cell)


def _docx_path(directory: Path, filename: str) -> Path:
    name = Path(filename)
    if name.name != filename or name.suffix.lower() != ".docx":
        raise ValueError("Укажите имя файла с расширением .docx без пути")
    path = directory / name
    if not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Файл находится за пределами рабочего каталога")
    return path


class DocumentGenerator:
    def __init__(
        self,
        templates_dir: Path = settings.templates_dir,
        output_dir: Path = settings.output_dir,
    ) -> None:
        self.templates_dir = Path(templates_dir).resolve()
        self.output_dir = Path(output_dir).resolve()

    def render_docx(self, template_name: str, context: dict, output_filename: str) -> str:
        source = _docx_path(self.templates_dir, template_name)
        destination = _docx_path(self.output_dir, output_filename)
        template = DocxTemplate(source)
        template.render(context, autoescape=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=self.output_dir) as temporary:
            rendered = Path(temporary) / destination.name
            template.save(rendered)
            rendered.replace(destination)
        return str(destination)

    def convert_to_pdf(self, docx_path: str) -> str | None:
        try:
            source = Path(docx_path).resolve(strict=True)
            if not source.is_file() or source.suffix.lower() != ".docx":
                raise ValueError("Ожидался файл DOCX")
            destination = source.with_suffix(".pdf")

            with TemporaryDirectory(dir=source.parent) as temporary:
                work_dir = Path(temporary)
                pdf = work_dir / destination.name
                system = platform.system()
                if system == "Windows":
                    from docx2pdf import convert

                    convert(str(source), str(pdf))
                elif system == "Linux":
                    office = shutil.which("libreoffice") or shutil.which("soffice")
                    if office is None:
                        raise RuntimeError("LibreOffice не найден в PATH")
                    profile = (work_dir / "profile").as_uri()
                    subprocess.run(
                        [
                            office,
                            f"-env:UserInstallation={profile}",
                            "--headless",
                            "--convert-to", "pdf",
                            "--outdir", str(work_dir),
                            str(source),
                        ],
                        check=True,
                        capture_output=True,
                        timeout=120,
                    )
                else:
                    raise RuntimeError(f"Конвертация для {system} не настроена")

                if not pdf.is_file() or pdf.stat().st_size == 0:
                    raise RuntimeError("Конвертер не создал PDF")
                pdf.replace(destination)
            return str(destination)
        except Exception as exc:
            logger.warning("Не удалось конвертировать DOCX в PDF (%s): %s", docx_path, exc)
            return None

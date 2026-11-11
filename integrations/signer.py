import logging
import re
from abc import ABC, abstractmethod
from base64 import b64encode
from pathlib import Path
from uuid import uuid4

from docusign_esign import (
    ApiClient,
    Document,
    EnvelopeDefinition,
    EnvelopesApi,
    Recipients,
    Signer,
    SignHere,
    Tabs,
)
from docusign_esign.client.api_exception import ApiException
from pydantic import BaseModel, ConfigDict, EmailStr

from config import settings


logger = logging.getLogger(__name__)
_MOCK_ID_PATTERN = re.compile(r"mock-[0-9a-f]{32}")


class SignatureRequest(BaseModel):
    """Без signing_anchor аккаунт DocuSign должен поддерживать свободную расстановку полей."""

    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)

    signer_email: EmailStr
    signer_name: str
    document_path: str
    contract_title: str
    signing_anchor: str | None = None


class SignatureStatus(BaseModel):
    envelope_id: str
    status: str
    signing_url: str | None = None


class BaseSignerService(ABC):
    @abstractmethod
    def send_for_signature(self, request: SignatureRequest) -> SignatureStatus:
        """Отправить документ на подпись."""

    @abstractmethod
    def get_status(self, envelope_id: str) -> SignatureStatus:
        """Получить состояние конверта по его идентификатору."""


class LocalSignerMock(BaseSignerService):
    def __init__(self, storage_dir: Path = settings.output_dir / "signature_mock") -> None:
        self.storage_dir = Path(storage_dir)

    def send_for_signature(self, request: SignatureRequest) -> SignatureStatus:
        if not Path(request.document_path).is_file():
            raise FileNotFoundError(request.document_path)

        envelope_id = f"mock-{uuid4().hex}"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        (self.storage_dir / envelope_id).touch(exist_ok=False)
        return self.get_status(envelope_id)

    def get_status(self, envelope_id: str) -> SignatureStatus:
        if not _MOCK_ID_PATTERN.fullmatch(envelope_id) or not (
            self.storage_dir / envelope_id
        ).is_file():
            raise LookupError(f"Тестовый конверт {envelope_id} не найден.")
        return SignatureStatus(
            envelope_id=envelope_id,
            status="sent",
            signing_url=f"https://docusign.example/sign/{envelope_id}",
        )


class DocuSignService(BaseSignerService):
    """DocuSign доставляет ссылку по email, поэтому signing_url в ответе может быть None."""

    def __init__(self, fallback: BaseSignerService | None = None) -> None:
        self.fallback = LocalSignerMock() if fallback is None else fallback
        self.account_id = settings.docusign_account_id.strip()
        token = settings.docusign_access_token.strip()
        self.api = None
        if self.account_id and token:
            client = ApiClient()
            client.host = settings.docusign_base_path.rstrip("/")
            client.set_default_header("Authorization", f"Bearer {token}")
            self.api = EnvelopesApi(client)

    def send_for_signature(self, request: SignatureRequest) -> SignatureStatus:
        if self.api is None:
            logger.warning("Учётные данные DocuSign отсутствуют. Используется тестовый режим.")
            return self.fallback.send_for_signature(request)

        path = Path(request.document_path)
        document = Document(
            document_base64=b64encode(path.read_bytes()).decode("ascii"),
            name=path.name,
            file_extension=path.suffix.lstrip(".").lower(),
            document_id="1",
        )
        signer = Signer(
            email=request.signer_email, name=request.signer_name, recipient_id="1"
        )
        if request.signing_anchor:
            signer.tabs = Tabs(sign_here_tabs=[
                SignHere(
                    document_id="1",
                    anchor_string=request.signing_anchor,
                    anchor_ignore_if_not_present="false",
                )
            ])
        envelope = EnvelopeDefinition(
            email_subject=request.contract_title,
            documents=[document],
            recipients=Recipients(signers=[signer]),
            status="sent",
        )
        try:
            result = self.api.create_envelope(self.account_id, envelope_definition=envelope)
        except ApiException as exc:
            if str(exc.status) != "401":
                raise
            logger.warning("DocuSign отклонил аутентификацию (401). Используется тестовый режим.")
            return self.fallback.send_for_signature(request)

        return SignatureStatus(envelope_id=result.envelope_id, status=result.status)

    def get_status(self, envelope_id: str) -> SignatureStatus:
        if _MOCK_ID_PATTERN.fullmatch(envelope_id):
            return self.fallback.get_status(envelope_id)
        if self.api is None:
            raise RuntimeError("Для проверки реального конверта нужны учётные данные DocuSign.")

        result = self.api.get_envelope(self.account_id, envelope_id)
        return SignatureStatus(envelope_id=envelope_id, status=result.status)

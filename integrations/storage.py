import logging
from abc import ABC, abstractmethod
from pathlib import Path
from shutil import copy2
from uuid import uuid4

from google.auth.exceptions import DefaultCredentialsError, MalformedError, RefreshError
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from config import settings


logger = logging.getLogger(__name__)
_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


class BaseStorageService(ABC):
    @abstractmethod
    def upload_file(self, file_path: str, folder_id: str | None = None) -> dict[str, str]:
        """Сохранить файл и вернуть его идентификатор и ссылку."""


class LocalStorageMock(BaseStorageService):
    def __init__(self, storage_dir: Path = settings.output_dir / "cloud_storage") -> None:
        self.storage_dir = Path(storage_dir)

    def upload_file(self, file_path: str, folder_id: str | None = None) -> dict[str, str]:
        source = Path(file_path)
        if not source.is_file():
            raise FileNotFoundError(file_path)

        file_id = f"mock-{uuid4().hex}"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        copy2(source, self.storage_dir / f"{file_id}-{source.name}")
        return {
            "file_id": file_id,
            "web_view_link": f"https://drive.google.com/file/d/{file_id}/view",
        }


class GoogleDriveStorage(BaseStorageService):
    def __init__(
        self,
        credentials_path: Path | None = None,
        fallback: BaseStorageService | None = None,
    ) -> None:
        self.credentials_path = Path(
            settings.google_service_account_file if credentials_path is None else credentials_path
        )
        self.fallback = LocalStorageMock() if fallback is None else fallback

    def upload_file(self, file_path: str, folder_id: str | None = None) -> dict[str, str]:
        source = Path(file_path)
        if not source.is_file():
            raise FileNotFoundError(file_path)

        folder_id = folder_id or settings.google_drive_folder_id
        if not self.credentials_path.is_file():
            logger.warning("Ключ Google Drive отсутствует. Используется локальное хранилище.")
            return self.fallback.upload_file(file_path, folder_id)

        try:
            credentials = Credentials.from_service_account_file(
                str(self.credentials_path), scopes=[_DRIVE_SCOPE]
            )
            with build("drive", "v3", credentials=credentials) as drive:
                return self._upload(drive, source, folder_id)
        except (DefaultCredentialsError, MalformedError, RefreshError, ValueError) as exc:
            logger.warning("Ошибка учётных данных Google Drive (%s).", type(exc).__name__)
        except HttpError as exc:
            if exc.resp.status != 401:
                raise
            logger.warning("Google Drive отклонил аутентификацию (401).")

        logger.warning("Используется локальное хранилище вместо Google Drive.")
        return self.fallback.upload_file(file_path, folder_id)

    @staticmethod
    def _upload(drive, source: Path, folder_id: str | None) -> dict[str, str]:
        metadata = {"name": source.name}
        if folder_id:
            metadata["parents"] = [folder_id]

        files = drive.files()
        uploaded = files.create(
            body=metadata,
            media_body=MediaFileUpload(str(source)),
            fields="id,webViewLink",
            supportsAllDrives=True,
        ).execute()
        file_id = uploaded["id"]
        try:
            drive.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader", "allowFileDiscovery": False},
                supportsAllDrives=True,
            ).execute()
        except Exception:
            try:
                files.update(
                    fileId=file_id, body={"trashed": True}, supportsAllDrives=True
                ).execute()
            except Exception:
                raise RuntimeError(
                    f"Не удалось открыть доступ к файлу Google Drive {file_id} "
                    "и переместить его в корзину."
                ) from None
            raise
        return {
            "file_id": file_id,
            "web_view_link": uploaded.get("webViewLink")
            or f"https://drive.google.com/open?id={file_id}",
        }

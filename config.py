from dataclasses import dataclass, field
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False, interpolate=False)


@dataclass(frozen=True)
class Settings:
    templates_dir: Path = BASE_DIR / "templates"
    output_dir: Path = BASE_DIR / "output"
    llm_api_key: str = field(default_factory=lambda: getenv("LLM_API_KEY", ""), repr=False)
    llm_base_url: str = field(
        default_factory=lambda: getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    )
    llm_model: str = field(default_factory=lambda: getenv("LLM_MODEL", "gpt-4o-mini"))
    telegram_bot_token: str = field(
        default_factory=lambda: getenv("TELEGRAM_BOT_TOKEN", ""), repr=False
    )
    docusign_account_id: str = field(
        default_factory=lambda: getenv("DOCUSIGN_ACCOUNT_ID", ""), repr=False
    )
    docusign_integration_key: str = field(
        default_factory=lambda: getenv("DOCUSIGN_INTEGRATION_KEY", ""), repr=False
    )
    google_service_account_file: Path = field(
        default_factory=lambda: BASE_DIR / Path(
            getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip() or "service_account.json"
        ).expanduser()
    )
    google_drive_folder_id: str = field(
        default_factory=lambda: getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    )
    docusign_access_token: str = field(
        default_factory=lambda: getenv("DOCUSIGN_ACCESS_TOKEN", ""), repr=False
    )
    docusign_base_path: str = field(
        default_factory=lambda: getenv("DOCUSIGN_BASE_PATH", "").strip()
        or "https://demo.docusign.net/restapi"
    )


settings = Settings()

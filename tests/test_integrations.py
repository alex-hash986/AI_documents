from base64 import b64decode
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from docusign_esign.client.api_exception import ApiException
from googleapiclient.errors import HttpError
from httplib2 import Response

from integrations import signer, storage


@pytest.fixture
def contract(tmp_path):
    source = tmp_path / "contract.docx"
    source.write_bytes(b"example contract")
    return source


@pytest.fixture
def signature_request(contract):
    return signer.SignatureRequest(
        signer_email="signer@example.org",
        signer_name="Подписант",
        document_path=str(contract),
        contract_title="Договор оказания услуг",
        signing_anchor="SIGN_HERE",
    )


@pytest.fixture
def drive_client(monkeypatch, tmp_path):
    key = tmp_path / "service_account.json"
    key.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(storage.Credentials, "from_service_account_file", Mock())
    drive = MagicMock()
    drive.__enter__.return_value = drive
    monkeypatch.setattr(storage, "build", Mock(return_value=drive))
    return key, drive


def test_google_drive_mock_without_key(contract, tmp_path, caplog):
    local = storage.LocalStorageMock(tmp_path / "cloud_storage")
    service = storage.GoogleDriveStorage(tmp_path / "missing.json", fallback=local)

    result = service.upload_file(str(contract), folder_id="../ignored-in-mock")

    file_id = result["file_id"]
    assert file_id.startswith("mock-")
    assert result["web_view_link"] == f"https://drive.google.com/file/d/{file_id}/view"
    assert (local.storage_dir / f"{file_id}-{contract.name}").read_bytes() == contract.read_bytes()
    assert "локальное хранилище" in caplog.text


def test_google_drive_upload_and_share(contract, drive_client):
    key, drive = drive_client
    files = drive.files.return_value
    files.create.return_value.execute.return_value = {
        "id": "remote-file", "webViewLink": "https://drive.google.com/file/d/remote-file/view"
    }

    result = storage.GoogleDriveStorage(key).upload_file(str(contract), "shared-folder")

    assert result == {
        "file_id": "remote-file",
        "web_view_link": "https://drive.google.com/file/d/remote-file/view",
    }
    request = files.create.call_args.kwargs
    assert request["body"] == {"name": contract.name, "parents": ["shared-folder"]}
    assert request["supportsAllDrives"] is True
    drive.permissions.return_value.create.assert_called_once_with(
        fileId="remote-file",
        body={"type": "anyone", "role": "reader", "allowFileDiscovery": False},
        supportsAllDrives=True,
    )


def test_google_drive_falls_back_on_auth_error(contract, drive_client, tmp_path):
    key, drive = drive_client
    drive.files.return_value.create.return_value.execute.side_effect = HttpError(
        Response({"status": "401"}), b"{}"
    )
    local = storage.LocalStorageMock(tmp_path / "cloud_storage")

    result = storage.GoogleDriveStorage(key, fallback=local).upload_file(str(contract))

    assert result["file_id"].startswith("mock-")
    drive.permissions.assert_not_called()


def test_google_drive_trashes_upload_when_sharing_is_denied(contract, drive_client):
    key, drive = drive_client
    files = drive.files.return_value
    files.create.return_value.execute.return_value = {"id": "remote-file"}
    drive.permissions.return_value.create.return_value.execute.side_effect = HttpError(
        Response({"status": "403"}), b"{}"
    )
    fallback = Mock()

    with pytest.raises(HttpError):
        storage.GoogleDriveStorage(key, fallback=fallback).upload_file(str(contract))

    files.update.assert_called_once_with(
        fileId="remote-file", body={"trashed": True}, supportsAllDrives=True
    )
    fallback.upload_file.assert_not_called()


def test_docusign_mock_without_credentials(signature_request, tmp_path, monkeypatch):
    monkeypatch.setattr(signer, "settings", SimpleNamespace(
        docusign_account_id="", docusign_access_token=""
    ))
    local = signer.LocalSignerMock(tmp_path / "signature_mock")
    service = signer.DocuSignService(fallback=local)

    result = service.send_for_signature(signature_request)

    assert result.envelope_id.startswith("mock-")
    assert result.status == "sent"
    assert result.signing_url.endswith(result.envelope_id)
    restored = signer.DocuSignService(fallback=signer.LocalSignerMock(local.storage_dir))
    assert restored.get_status(result.envelope_id) == result
    with pytest.raises(LookupError):
        service.get_status("mock-" + "0" * 32)


@pytest.fixture
def docusign_client(monkeypatch):
    monkeypatch.setattr(signer, "settings", SimpleNamespace(
        docusign_account_id="account",
        docusign_access_token="test-token",
        docusign_base_path="https://demo.docusign.net/restapi",
    ))
    api = Mock()
    monkeypatch.setattr(signer, "EnvelopesApi", Mock(return_value=api))
    return api


def test_docusign_sends_envelope_and_checks_status(signature_request, contract, docusign_client):
    docusign_client.create_envelope.return_value = SimpleNamespace(
        envelope_id="envelope", status="sent"
    )
    docusign_client.get_envelope.return_value = SimpleNamespace(status="completed")
    service = signer.DocuSignService()

    sent = service.send_for_signature(signature_request)
    completed = service.get_status(sent.envelope_id)

    envelope = docusign_client.create_envelope.call_args.kwargs["envelope_definition"]
    assert envelope.status == "sent"
    assert b64decode(envelope.documents[0].document_base64) == contract.read_bytes()
    assert envelope.documents[0].file_extension == "docx"
    recipient = envelope.recipients.signers[0]
    assert recipient.email == signature_request.signer_email
    assert recipient.tabs.sign_here_tabs[0].anchor_string == "SIGN_HERE"
    assert sent.signing_url is None
    assert completed.status == "completed"
    docusign_client.get_envelope.assert_called_once_with("account", "envelope")


def test_docusign_falls_back_only_on_auth_error(
    signature_request, docusign_client, tmp_path
):
    local = signer.LocalSignerMock(tmp_path / "signature_mock")
    service = signer.DocuSignService(fallback=local)
    docusign_client.create_envelope.side_effect = ApiException(status=401)
    assert service.send_for_signature(signature_request).envelope_id.startswith("mock-")

    docusign_client.create_envelope.side_effect = ApiException(status=503)
    with pytest.raises(ApiException):
        service.send_for_signature(signature_request)

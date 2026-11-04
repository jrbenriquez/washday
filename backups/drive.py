"""Small Drive client; credentials and raw provider errors never reach logs/UI."""

import json
import re
import uuid
import requests
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

SCOPE = "openid email https://www.googleapis.com/auth/drive.file"
FOLDER_MIME = "application/vnd.google-apps.folder"


class DriveError(Exception):
    pass


def cipher():
    try:
        return Fernet(settings.GOOGLE_DRIVE_TOKEN_KEY.encode())
    except (ValueError, TypeError):
        raise DriveError(
            "Configure a valid GOOGLE_DRIVE_TOKEN_KEY on the web server and worker."
        ) from None


def configured():
    return bool(
        settings.GOOGLE_DRIVE_CLIENT_ID
        and settings.GOOGLE_DRIVE_CLIENT_SECRET
        and settings.GOOGLE_DRIVE_REDIRECT_URI
        and settings.GOOGLE_DRIVE_TOKEN_KEY
    )


def encrypt(token):
    return cipher().encrypt(token.encode()).decode()


def decrypt(token):
    try:
        return cipher().decrypt(token.encode()).decode()
    except InvalidToken:
        raise DriveError(
            "The Drive token cannot be decrypted. Restore the token key or reconnect Drive."
        ) from None


def http(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=(10, 60), **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}
    except (requests.RequestException, ValueError):
        raise DriveError(
            "Google Drive request failed. Check connectivity, folder access and consent; reconnect if needed."
        ) from None


def tokens(**params):
    return http(
        "POST",
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
            "client_secret": settings.GOOGLE_DRIVE_CLIENT_SECRET,
            **params,
        },
    )


class DriveClient:
    def __init__(self, backup):
        data = tokens(
            grant_type="refresh_token",
            refresh_token=decrypt(backup.refresh_token_encrypted),
        )
        if not data.get("access_token"):
            raise DriveError("Reconnect Google Drive to renew access.")
        self.access_token = data["access_token"]

    def request(self, method, path, **kwargs):
        headers = {
            "Authorization": "Bearer " + self.access_token,
            **kwargs.pop("headers", {}),
        }
        return http(
            method, "https://www.googleapis.com/" + path, headers=headers, **kwargs
        )

    def folder(self, folder_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", folder_id):
            raise DriveError("Choose a valid Google Drive folder.")
        folder = self.request(
            "GET",
            "drive/v3/files/" + folder_id,
            params={"fields": "id,name,mimeType,trashed,capabilities(canAddChildren)"},
        )
        if (
            folder.get("mimeType") != FOLDER_MIME
            or folder.get("trashed")
            or not folder.get("capabilities", {}).get("canAddChildren")
        ):
            raise DriveError("Choose a writable folder that is not in the trash.")
        return folder

    def create_folder(self, name, parent=None, run_key=None):
        body = {"name": name, "mimeType": FOLDER_MIME}
        if parent:
            body["parents"] = [parent]
        if run_key:
            body["appProperties"] = {"washdayRun": run_key}
        return self.request(
            "POST", "drive/v3/files", json=body, params={"fields": "id,name"}
        )

    def run_folder(self, parent, name, run_key):
        self.folder(parent)
        found = self.request(
            "GET",
            "drive/v3/files",
            params={
                "q": f"'{parent}' in parents and trashed = false and appProperties has {{ key='washdayRun' and value='{run_key}' }}",
                "fields": "files(id,name)",
            },
        ).get("files", [])
        return found[0] if found else self.create_folder(name, parent, run_key)

    def upload(self, folder_id, filename, content, mime):
        # Reuse the same file on retry, including after an upload succeeded but the response was lost.
        found = self.request(
            "GET",
            "drive/v3/files",
            params={
                "q": f"'{folder_id}' in parents and trashed = false and name = '{filename}'",
                "fields": "files(id)",
            },
        ).get("files", [])
        if found:
            return self.request(
                "PATCH",
                "upload/drive/v3/files/" + found[0]["id"],
                params={"uploadType": "media"},
                data=content,
                headers={"Content-Type": mime},
            )
        metadata = json.dumps({"name": filename, "parents": [folder_id]})
        boundary = "washday_" + uuid.uuid4().hex
        body = (
            (
                f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{metadata}\r\n"
                f"--{boundary}\r\nContent-Type: {mime}\r\n\r\n"
            ).encode()
            + content
            + f"\r\n--{boundary}--\r\n".encode()
        )
        return self.request(
            "POST",
            "upload/drive/v3/files",
            params={"uploadType": "multipart"},
            data=body,
            headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        )

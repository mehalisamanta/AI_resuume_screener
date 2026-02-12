"""
SharePoint Integration Module - Updated with Microsoft Graph API (MSAL)
Uses App-Only authentication via Azure AD for robust enterprise connectivity.
"""

import streamlit as st
import io
import os
import requests
from datetime import datetime

# ── Dependency Check
SHAREPOINT_AVAILABLE = False
SHAREPOINT_ERROR = None

try:
    import msal
    SHAREPOINT_AVAILABLE = True
except ImportError as e:
    SHAREPOINT_AVAILABLE = False
    SHAREPOINT_ERROR = str(e)
except Exception as e:
    SHAREPOINT_AVAILABLE = False
    SHAREPOINT_ERROR = f"Unexpected error: {str(e)}"


# ── SharePoint Uploader Class 

class SharePointUploader:
    """Handles Microsoft Graph API interactions for SharePoint."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = self._get_access_token()

    def _get_access_token(self) -> str:
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=self.client_secret
        )
        token_response = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in token_response:
            raise Exception(f"Auth failed: {token_response.get('error_description', 'Unknown error')}")
        return token_response["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    # Upload
    def upload_file(
        self,
        site_id: str,
        drive_id: str,
        folder_path: str,
        file_name: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict:
        clean_path = folder_path.strip("/")
        url = (
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/drives/{drive_id}/root:/{clean_path}/{file_name}:/content"
        )
        headers = {**self._headers(), "Content-Type": content_type}
        response = requests.put(url, headers=headers, data=content)
        if response.status_code not in (200, 201):
            raise Exception(f"Upload failed [{response.status_code}]: {response.text}")
        return response.json()

    def upload_csv(
        self, site_id: str, drive_id: str, folder_path: str, file_name: str, df
    ) -> dict:
        import pandas as pd
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        content = buf.getvalue().encode("utf-8")
        return self.upload_file(site_id, drive_id, folder_path, file_name, content, "text/csv")

    # ── List & Download ─────────────────────────────────────────────────────
    def list_files(self, site_id: str, drive_id: str, folder_path: str) -> list:
        clean_path = folder_path.strip("/")
        url = (
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/drives/{drive_id}/root:/{clean_path}:/children"
        )
        response = requests.get(url, headers=self._headers())
        if response.status_code != 200:
            raise Exception(f"List failed [{response.status_code}]: {response.text}")
        items = response.json().get("value", [])
        # Return only files (not folders)
        return [i for i in items if "file" in i]

    def download_file(self, download_url: str) -> bytes:
        """Download using the @microsoft.graph.downloadUrl provided in list results."""
        response = requests.get(download_url)
        response.raise_for_status()
        return response.content


# ── Streamlit-aware helper functions ──────────────────────────────────────────

def _make_uploader(config: dict) -> SharePointUploader:
    """Build an uploader from the session config dict."""
    return SharePointUploader(
        tenant_id=config["tenant_id"],
        client_id=config["client_id"],
        client_secret=config["client_secret"],
    )


def connect_to_sharepoint(tenant_id: str, client_id: str, client_secret: str) -> dict | None:
    """
    Authenticate and return a config dict that can be stored in session state.
    Returns None on failure.
    """
    try:
        uploader = SharePointUploader(tenant_id, client_id, client_secret)
        # Quick connectivity probe – list root of the drive
        site_id = st.session_state.sharepoint_config.get("site_id", "")
        drive_id = st.session_state.sharepoint_config.get("drive_id", "")
        if site_id and drive_id:
            uploader.list_files(site_id, drive_id, "/")
        return uploader  # Return the object; callers store it
    except Exception as e:
        st.error(f"SharePoint connection error: {str(e)}")
        return None


def upload_to_sharepoint(config: dict, file_content: bytes, file_name: str) -> bool:
    """Upload a single file using Graph API."""
    try:
        uploader = _make_uploader(config)
        uploader.upload_file(
            site_id=config["site_id"],
            drive_id=config["drive_id"],
            folder_path=config["folder_path"],
            file_name=file_name,
            content=file_content,
        )
        return True
    except Exception as e:
        st.error(f"Upload error: {str(e)}")
        return False


def download_from_sharepoint(config: dict) -> list:
    """
    Download all supported resume files from the configured folder.
    Returns list of dicts: {name, content, timestamp}
    """
    try:
        uploader = _make_uploader(config)
        items = uploader.list_files(
            site_id=config["site_id"],
            drive_id=config["drive_id"],
            folder_path=config["folder_path"],
        )

        downloaded = []
        for item in items:
            name = item.get("name", "")
            ext = name.rsplit(".", 1)[-1].lower()
            if ext not in ("pdf", "docx"):
                continue

            dl_url = item.get("@microsoft.graph.downloadUrl")
            if not dl_url:
                continue

            content = uploader.download_file(dl_url)
            timestamp = item.get("createdDateTime", datetime.now().isoformat())
            downloaded.append({"name": name, "content": content, "timestamp": timestamp})

        return downloaded
    except Exception as e:
        st.error(f"Download error: {str(e)}")
        return []


def save_csv_to_sharepoint(config: dict, df, filename: str) -> bool:
    """Save a DataFrame as CSV to SharePoint."""
    try:
        uploader = _make_uploader(config)
        uploader.upload_csv(
            site_id=config["site_id"],
            drive_id=config["drive_id"],
            folder_path=config["folder_path"],
            file_name=filename,
            df=df,
        )
        return True
    except Exception as e:
        st.error(f"Error saving CSV to SharePoint: {str(e)}")
        return False
import msal
import requests
import io
import streamlit as st

class SharePointUploader:
    def __init__(self, tenant_id, client_id, client_secret):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = self._get_access_token()

    def _get_access_token(self):
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.ConfidentialClientApplication(
            self.client_id, authority=authority, client_credential=self.client_secret
        )
        token_response = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in token_response:
            raise Exception("Auth failed. Check your Azure Secrets.")
        return token_response["access_token"]

    def resolve_site_and_drive(self, sharepoint_url: str):
        """Converts a user-provided URL into Site and Drive IDs"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        # 1. Extract hostname and relative path from the URL
        # Example: https://tenant.sharepoint.com/sites/Marketing
        from urllib.parse import urlparse
        parsed = urlparse(sharepoint_url)
        hostname = parsed.netloc
        # Extract path like "/sites/Marketing"
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            raise ValueError("Invalid SharePoint URL format.")
        relative_path = f"/{path_parts[0]}/{path_parts[1]}"

        # 2. Get Site ID
        site_url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:{relative_path}"
        site_res = requests.get(site_url, headers=headers).json()
        if "id" not in site_res:
            raise Exception(f"Could not find SharePoint Site: {site_res.get('error')}")
        site_id = site_res["id"]

        # 3. Get Default Drive ID
        drive_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive"
        drive_res = requests.get(drive_url, headers=headers).json()
        if "id" not in drive_res:
            raise Exception("Could not find default Document Library.")
        
        return site_id, drive_res["id"]

    def upload_csv(self, site_id, drive_id, file_name, csv_buffer):
        upload_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{file_name}:/content"
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "text/csv"}
        response = requests.put(upload_url, headers=headers, data=csv_buffer.getvalue())
        return response.status_code in [200, 201]
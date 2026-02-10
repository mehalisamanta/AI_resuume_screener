import msal
import requests
<<<<<<< HEAD
from urllib.parse import urlparse
=======
import io

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

>>>>>>> dev-branch

class SharePointUploader:
    def __init__(self, tenant_id, client_id, client_secret):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = self._get_access_token()

    def _get_access_token(self):
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=self.client_secret
        )
<<<<<<< HEAD
        token_response = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in token_response:
            raise Exception(f"Auth failed: {token_response.get('error_description')}")
        return token_response["access_token"]

    def resolve_site_and_drive(self, sharepoint_url: str):
        """Converts user URL to IDs needed for upload"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        parsed = urlparse(sharepoint_url)
        hostname = parsed.netloc
        path_parts = parsed.path.strip("/").split("/")
        
        if len(path_parts) < 2:
            raise ValueError("URL too short. Use format: https://tenant.sharepoint.com/sites/SiteName")
        
        relative_path = f"/{path_parts[0]}/{path_parts[1]}"
        
        # Get Site ID
        site_url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:{relative_path}"
        site_res = requests.get(site_url, headers=headers).json()
        if "id" not in site_res:
            raise Exception("Site not found. Check your URL.")
            
        site_id = site_res["id"]

        # Get default Drive ID
        drive_res = requests.get(f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive", headers=headers).json()
        return site_id, drive_res.get("id")

    def upload_csv_to_sharepoint(self, site_id, drive_id, folder_path, file_name, csv_buffer):
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{folder_path}/{file_name}:/content"
=======

        token_response = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )

        if "access_token" not in token_response:
            raise Exception(f"Auth failed: {token_response}")

        return token_response["access_token"]

    def upload_csv_to_sharepoint(
        self,
        site_id: str,
        drive_id: str,
        folder_path: str,
        file_name: str,
        csv_buffer: io.BytesIO
    ):
        upload_url = (
            f"{GRAPH_API_ENDPOINT}/sites/{site_id}"
            f"/drives/{drive_id}"
            f"/root:/{folder_path}/{file_name}:/content"
        )

>>>>>>> dev-branch
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "text/csv"
        }
<<<<<<< HEAD
        response = requests.put(url, headers=headers, data=csv_buffer.getvalue())
        if response.status_code not in [200, 201]:
            raise Exception(f"Upload error: {response.text}")
        return True
=======

        response = requests.put(
            upload_url,
            headers=headers,
            data=csv_buffer.getvalue()
        )

        if response.status_code not in [200, 201]:
            raise Exception(
                f"Upload failed: {response.status_code} {response.text}"
            )

        return response.json()
>>>>>>> dev-branch

import msal
import requests
import io

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


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

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "text/csv"
        }

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

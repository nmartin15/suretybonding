from dataclasses import dataclass

import requests


@dataclass
class ApiClient:
    """Thin wrapper around requests with auth and base URL."""

    base_url: str
    token: str

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get(self, path: str, **kwargs) -> requests.Response:
        return requests.get(f"{self.base_url}{path}", headers=self._headers(), **kwargs)

    def post(
        self, path: str, json_body: dict | None = None, **kwargs
    ) -> requests.Response:
        return requests.post(
            f"{self.base_url}{path}", headers=self._headers(), json=json_body, **kwargs
        )

    def patch(self, path: str, json_body: dict, **kwargs) -> requests.Response:
        return requests.patch(
            f"{self.base_url}{path}", headers=self._headers(), json=json_body, **kwargs
        )

    def post_multipart(
        self, path: str, files: dict, data: dict | None = None
    ) -> requests.Response:
        headers = {"Authorization": f"Bearer {self.token}"}
        return requests.post(
            f"{self.base_url}{path}", headers=headers, files=files, data=data
        )

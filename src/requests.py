from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import request


@dataclass
class Response:
    status: int
    body: bytes

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise RuntimeError(f"HTTP error {self.status}")

    def json(self):
        return json.loads(self.body.decode("utf-8"))


def post(url: str, json: dict, timeout: int = 60) -> Response:
    payload = bytes(__import__("json").dumps(json), encoding="utf-8")
    req = request.Request(url=url, data=payload, method="POST", headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=timeout) as resp:
        return Response(status=resp.status, body=resp.read())

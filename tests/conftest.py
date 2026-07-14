"""Shared test helpers: a tiny fake requests.Session."""

import json as _json


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text else (_json.dumps(payload) if payload is not None else "")

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    """Records requests and returns queued/callback responses."""

    def __init__(self, handler=None, response=None):
        self.handler = handler
        self.response = response
        self.calls = []

    def _respond(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if self.handler is not None:
            return self.handler(method, url, **kwargs)
        return self.response

    def get(self, url, **kwargs):
        return self._respond("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._respond("POST", url, **kwargs)

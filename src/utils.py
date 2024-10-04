"""
Utility functions.
"""

import hashlib
import json
import re
from collections import defaultdict
from contextlib import contextmanager
from unittest.mock import patch

import requests


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove special characters.
    """
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", filename)
    filename = filename.strip().strip(". ")
    return filename


def hash_request(url, params=None):
    """Creates a hash for the given URL and query parameters."""
    hash_input = url
    if params:
        _params = params.copy()
        if "token" in _params:
            _params["token"] = ""
        if "expiration" in _params:
            _params["expiration"] = ""
        hash_input += json.dumps(_params, sort_keys=True)

    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


@contextmanager
def mock_requests(cache_file="responses.jsonl", load=False):
    """Mock requests.get to cache / load responses."""
    cache = defaultdict(list)
    file_mode = "w" if not load else "r"

    with open(cache_file, file_mode) as file:
        if load:
            file.seek(0)
            for line in file:
                entry = json.loads(line)
                cache[entry["hash"]].append(entry["response"])

        def mock_get(url, *args, **kwargs):
            params = kwargs.get("params")
            request_hash = hash_request(url, params=params)
            if load:
                return MockResponse(cache[request_hash].pop(0), 200)

            with requests.Session() as session:
                response = session.get(url, *args, **kwargs)

                try:
                    response_json = response.json()
                    for sensitive_key in [
                        "clientHashId",
                        "deviceSessionToken",
                        "eid",
                        "kindleSessionId",
                    ]:
                        if sensitive_key in response_json:
                            response_json[sensitive_key] = ""
                    text = json.dumps(response_json)
                except json.JSONDecodeError:
                    text = response.text

                cache[request_hash].append(text)
                file.write(
                    json.dumps({"hash": request_hash, "response": text}) + "\n"
                )
                file.flush()

            return MockResponse(response.text, response.status_code)

        with patch("requests.get", side_effect=mock_get):
            yield


class MockResponse:
    """Mock response object for requests."""

    def __init__(self, text, status_code):
        self.text = text
        self.status_code = status_code

    def json(self):
        return json.loads(self.text)

    @property
    def content(self):
        return self.text.encode("utf-8")

#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Fork: MangaDex gets Comicarr's own User-Agent, never the browser-like one."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

import comicarr
from comicarr import mangadex

BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"


def test_requests_carry_comicarr_and_not_the_comicvine_agent(monkeypatch):
    monkeypatch.setattr(comicarr, "CONFIG", SimpleNamespace(CV_USER_AGENT=BROWSER), raising=False)
    monkeypatch.setattr(comicarr, "CURRENT_VERSION", "abc123", raising=False)
    answer = MagicMock(status_code=200)
    answer.json.return_value = {"result": "ok"}

    with patch("comicarr.mangadex._rate_limit"), patch("comicarr.mangadex.requests.get", return_value=answer) as get:
        assert mangadex._make_request("/manga", params={"title": "Uzumaki"}) == {"result": "ok"}

    agent = get.call_args.kwargs["headers"]["User-Agent"]
    assert agent.startswith("Comicarr/abc123")
    assert "Mozilla" not in agent


def test_an_html_answer_is_logged_with_what_came_back(monkeypatch):
    monkeypatch.setattr(comicarr, "CONFIG", SimpleNamespace(CV_USER_AGENT=BROWSER), raising=False)
    answer = MagicMock(status_code=200, text="<html><body>Checking your browser</body></html>")
    answer.headers = {"Content-Type": "text/html"}
    answer.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)

    with (
        patch("comicarr.mangadex._rate_limit"),
        patch("comicarr.mangadex.requests.get", return_value=answer),
        patch.object(mangadex.logger, "error") as error,
    ):
        assert mangadex._make_request("/manga") is None

    message = error.call_args.args[0]
    assert "HTTP 200 with text/html instead of JSON" in message
    assert "Checking your browser" in message

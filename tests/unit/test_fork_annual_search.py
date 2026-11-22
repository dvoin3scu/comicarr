"""Fork: the annual lookup calls findComic with a keyword it accepts.

v0.65.0 (#1471) renamed comic_add's annual_check to check_annuals, and the
sweep also renamed the findComic keyword. Adding or refreshing any series with
"Include annuals" on failed with "unexpected keyword argument 'check_annuals'"
and left the series without issues. Drop this patch once upstream fixes the call.
"""

import inspect

from sqlalchemy import create_engine

from comicarr.app.search import mb
from comicarr.app.series import comic_add


def test_check_annuals_calls_find_comic_with_accepted_keywords(monkeypatch):
    engine = create_engine("sqlite://")
    comic_add.annuals.metadata.create_all(engine, tables=[comic_add.annuals])
    monkeypatch.setattr(comic_add.db, "get_engine", lambda: engine)
    calls = []

    def fake_find(*args, **kwargs):
        inspect.signature(mb.findComic).bind(*args, **kwargs)  # TypeError on an unknown keyword
        calls.append(kwargs)
        return None

    monkeypatch.setattr(comic_add.mb, "findComic", fake_find)

    comic_add.check_annuals("BRZRKR", "2021", "178058", [], [], [], "Continuing")

    assert calls == [{"issue": None, "annual_check": True}]

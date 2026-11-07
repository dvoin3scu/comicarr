#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Fork: the ComicInfo <SeriesGroup> a Series is tagged with."""

import json
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup as Soup

import comicarr
from comicarr import cmtag, cv, db
from comicarr.app.series import fork_router, series_group
from comicarr.db import get_engine, shutdown_engine
from comicarr.tables import metadata

DIE = "117000"
HEARTBREAKER = "119531"
SPLIT = "124800"


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(comicarr, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(comicarr, "CONFIG", SimpleNamespace(ANNUALS_ON=False), raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    shutdown_engine()
    metadata.create_all(get_engine())
    yield tmp_path
    shutdown_engine()


def _series(comic_id, name, booktype="Print", collects=None, location="/comics/x"):
    db.upsert(
        "comics",
        {
            "ComicName": name,
            "Type": booktype,
            "Collects": json.dumps(collects) if collects is not None else None,
            "ComicLocation": location,
            "Status": "Active",
        },
        {"ComicID": comic_id},
    )


def _die_family():
    _series(DIE, "Die")
    _series(
        HEARTBREAKER,
        "Die: Fantasy Heartbreaker",
        "TPB",
        [{"series": "DIE", "comicid": "4050-" + DIE, "issueid": None, "issues": "#1-5"}],
    )
    _series(SPLIT, "Die: Split the Party", "TPB")


def test_a_collected_edition_takes_the_name_of_the_series_it_collects(library):
    _die_family()
    assert series_group.resolve(HEARTBREAKER) == {"value": "Die", "source": "collects", "chosen": False}


def test_a_collected_edition_without_collects_falls_back_to_its_name_before_the_colon(library):
    _die_family()
    assert series_group.resolve(SPLIT)["value"] == "Die"
    assert series_group.resolve(SPLIT)["source"] == "name"


def test_the_single_issues_join_the_group_their_editions_point_at(library):
    _die_family()
    assert series_group.resolve(DIE) == {"value": "Die", "source": "parent", "chosen": False}


def test_a_print_series_with_a_colon_gets_no_group_of_its_own(library):
    _series("1", "Batman: The Long Halloween")
    assert series_group.resolve("1")["value"] is None


def test_collects_naming_a_series_outside_the_library_uses_its_linked_name(library):
    _series("2", "Saga Vol. 1", "TPB", [{"series": "Saga", "comicid": "4050-999", "issues": "#1-6"}])
    assert series_group.resolve("2")["value"] == "Saga"


def test_a_chosen_group_wins_and_none_clears(library):
    _die_family()
    series_group.set_choice(SPLIT, "  The   DIE saga ")
    assert series_group.resolve(SPLIT) == {"value": "The DIE saga", "source": "chosen", "chosen": True}

    series_group.set_choice(SPLIT, "")
    assert series_group.resolve(SPLIT) == {"value": None, "source": "none", "chosen": True}
    assert series_group.group_for_tagging(SPLIT) == ""

    series_group.set_choice(SPLIT, None)
    assert series_group.resolve(SPLIT)["source"] == "name"
    stored = json.loads((library / series_group.FILE_NAME).read_text())
    assert SPLIT not in stored


def test_an_unknown_group_leaves_the_file_alone(library):
    _series("3", "Wizard")
    assert series_group.group_for_tagging("3") is None


def test_an_unreadable_store_is_ignored(library):
    (library / series_group.FILE_NAME).write_text("{not json")
    _die_family()
    assert series_group.resolve(SPLIT)["value"] == "Die"


def test_the_tag_line_carries_the_group_escaped(library):
    _die_family()
    db.upsert("issues", {"ComicID": SPLIT, "Issue_Number": "1"}, {"IssueID": "500"})
    series_group.set_choice(SPLIT, "Die, Vol=2")

    assert cmtag.series_group_field("500") == "seriesGroup=Die^, Vol^=2"
    assert cmtag.series_group_field("unknown") is None
    assert cmtag.series_group_field(None) is None


def test_routes_read_and_choose_the_group(library):
    _die_family()

    assert fork_router.get_series_group(SPLIT)["value"] == "Die"
    assert fork_router.update_series_group(SPLIT, {"value": "Die Family"})["value"] == "Die Family"
    assert fork_router.update_series_group(SPLIT, {}).status_code == 400
    assert fork_router.update_series_group(SPLIT, {"value": 3}).status_code == 400
    assert fork_router.update_series_group("404", {"value": None}).status_code == 404
    assert fork_router.get_series_group("404").status_code == 404


DIE_SPLIT_DESCRIPTION = (
    "<p>No one can escape <a data-ref-id='4050-1'>DIE</a> until everyone agrees to go home. "
    "A sequel to <a data-ref-id='4050-2'>Other</a>. They'll never escape themselves."
    "Collects <a href='/die/4050-117000/' data-ref-id='4050-117000'>DIE</a> #6-10. "
    "Written by <a data-ref-id='4040-5'>Kieron Gillen</a> and <a data-ref-id='4050-3'>Nope</a>.</p>"
)


def test_collects_is_found_anywhere_in_the_description(library):
    soup = Soup(DIE_SPLIT_DESCRIPTION, "html.parser")
    links = cv.collected_edition_links(cv.drophtml(DIE_SPLIT_DESCRIPTION), soup)
    assert [link["data-ref-id"] for link in links] == ["4050-117000"]


def test_the_old_trade_paperback_opening_still_returns_every_link(library):
    html = "<p>Trade paperback collecting <a data-ref-id='4050-7'>X</a> and <a data-ref-id='4005-1'>Y</a></p>"
    links = cv.collected_edition_links(cv.drophtml(html), Soup(html, "html.parser"))
    assert len(links) == 2


def test_a_description_without_collects_has_no_links(library):
    html = "<p>The sequel to <a data-ref-id='4050-7'>X</a>.</p>"
    assert cv.collected_edition_links(cv.drophtml(html), Soup(html, "html.parser")) == []
    assert cv.collected_edition_links("None", None) == []

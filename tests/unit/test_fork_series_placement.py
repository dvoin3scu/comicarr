#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Fork: the same series folder under another library root."""

import json
import queue
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import comicarr
from comicarr import db, importer
from comicarr.app.search import service as search_service
from comicarr.app.series import fork_router
from comicarr.app.series import location as series_location
from comicarr.app.series import service as series_service
from comicarr.db import get_engine, shutdown_engine
from comicarr.tables import metadata

DIE = "119531"


@pytest.fixture
def library(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    comics_root = tmp_path / "comics"
    collected_root = tmp_path / "comics-collected"
    manga_root = tmp_path / "manga"
    for root in (comics_root, collected_root, manga_root):
        root.mkdir()
    config = SimpleNamespace(
        DESTINATION_DIR=str(comics_root),
        MANGA_DESTINATION_DIR=str(manga_root),
        MAGAZINE_DESTINATION_DIR=None,
        COMIC_DIR=None,
        MANGA_DIR=None,
        MULTIPLE_DEST_DIRS=None,
        NEWCOM_DIR=None,
        ADDITIONAL_LIBRARY_ROOTS="%s\n%s" % (collected_root, comics_root / "nested"),
        FOLDER_FORMAT="$Publisher/$Series",
        REPLACE_SPACES=False,
        FORMAT_BOOKTYPE=False,
        ANNUALS_ON=False,
        CREATE_FOLDERS=False,
    )
    monkeypatch.setattr(comicarr, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(comicarr, "CONFIG", config, raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    shutdown_engine()
    metadata.create_all(get_engine())
    monkeypatch.setattr("comicarr.updater.forceRescan", lambda comic_id, **kwargs: None)
    yield SimpleNamespace(
        ctx=SimpleNamespace(config=config),
        config=config,
        comics=comics_root,
        collected=collected_root,
        manga=manga_root,
    )
    shutdown_engine()


def _add_series(comic_id, name, location, **extra):
    values = {
        "ComicName": name,
        "ComicYear": "2019",
        "ComicPublisher": "Image",
        "Type": "Print",
        "Status": "Active",
        "ComicLocation": str(location) if location else None,
        **extra,
    }
    db.upsert("comics", values, {"ComicID": comic_id})


def test_placement_roots_are_the_destinations_then_the_extra_roots(library):
    assert series_location.placement_roots(library.config) == [
        str(library.comics),
        str(library.manga),
        str(library.collected),
        str(library.comics / "nested"),
    ]


def test_rebase_keeps_the_path_below_its_own_root(library):
    rebased = series_location.rebase_onto_root(
        str(library.comics / "Image" / "Die"), str(library.collected), library.config
    )
    assert rebased == str(library.collected / "Image" / "Die")


def test_rebase_uses_the_deepest_root_holding_the_path(library):
    rebased = series_location.rebase_onto_root(
        str(library.comics / "nested" / "Image" / "Die"), str(library.collected), library.config
    )
    assert rebased == str(library.collected / "Image" / "Die")


def test_rebase_of_a_path_outside_every_root_keeps_its_last_part(library, tmp_path):
    rebased = series_location.rebase_onto_root(
        str(tmp_path / "elsewhere" / "Die"), str(library.collected), library.config
    )
    assert rebased == str(library.collected / "Die")


def test_folder_options_list_the_automatic_folder_first_then_each_root(library):
    _add_series(DIE, "Die", library.comics / "Image" / "Die")

    options = series_location.folder_options(DIE, library.config)

    assert options["automatic"] == str(library.comics / "Image" / "Die")
    assert options["options"][0] == {
        "root": str(library.comics),
        "folder": str(library.comics / "Image" / "Die"),
        "automatic": True,
    }
    folders = [option["folder"] for option in options["options"]]
    assert str(library.collected / "Image" / "Die") in folders
    assert str(library.manga / "Image" / "Die") in folders
    assert len(folders) == len(set(folders))


def test_folder_options_for_an_unknown_series_is_a_404(library):
    with pytest.raises(series_location.SeriesLocationError) as refused:
        series_location.folder_options("404", library.config)
    assert refused.value.status == 404


def test_an_add_accepts_a_root_or_a_folder_but_not_both(library):
    folder, root = series_location.new_series_placement(DIE, None, str(library.collected) + "/", library.config)
    assert (folder, root) == (None, str(library.collected))

    with pytest.raises(series_location.SeriesLocationError, match="not both"):
        series_location.new_series_placement(
            DIE, str(library.collected / "Die"), str(library.collected), library.config
        )

    with pytest.raises(series_location.SeriesLocationError, match="library roots"):
        series_location.new_series_placement(DIE, None, "/srv/elsewhere", library.config)


@pytest.mark.parametrize(
    "add",
    [
        lambda ctx, root: series_service.add_comic(ctx, "4050-" + DIE, root=root),
        lambda ctx, root: search_service.add_comic(ctx, DIE, root=root),
    ],
    ids=["series", "search"],
)
def test_every_comic_add_queues_the_chosen_root(library, add):
    with patch("comicarr.importer.importer_thread") as thread:
        result = add(library.ctx, str(library.collected))

    assert result["success"] is True
    watch = thread.call_args.args[0][0]
    assert watch["root"] == str(library.collected)
    assert "location" not in watch


def test_the_add_queue_places_the_new_series_under_its_root(library):
    def fake_add(comic_id, **kwargs):
        _add_series(DIE, "Die", library.comics / "Image" / "Die")
        (library.comics / "Image" / "Die").mkdir(parents=True)

    series_queue = queue.Queue()
    series_queue.put({"comicid": DIE, "comicname": None, "root": str(library.collected)})
    series_queue.put("exit")

    with patch("comicarr.importer.addComictoDB", side_effect=fake_add), patch("comicarr.importer.time.sleep"):
        importer.addvialist(series_queue, queue.Queue())

    row = db.raw_select_one("SELECT ComicLocation, dirlocked FROM comics WHERE ComicID=?", [DIE])
    assert row["ComicLocation"] == str(library.collected / "Image" / "Die")
    assert int(row["dirlocked"]) == 1
    assert (library.collected / "Image" / "Die").is_dir()
    assert not (library.comics / "Image").exists()


def test_a_busy_library_is_retried_before_placing(library, monkeypatch):
    _add_series(DIE, "Die", library.comics / "Image" / "Die")
    calls = []
    real_change = series_location.change_series_location

    def busy_once(ctx, comic_id, folder, move_files=False):
        calls.append(folder)
        if len(calls) == 1:
            raise series_location.SeriesLocationError("busy", status=409)
        return real_change(ctx, comic_id, folder, move_files=move_files)

    monkeypatch.setattr(series_location, "change_series_location", busy_once)
    result = series_location.place_under_root(DIE, str(library.collected), wait=0)

    assert result["success"] is True
    assert len(calls) == 2


def test_a_failed_placement_never_fails_the_add(library):
    with patch.object(series_location, "place_under_root", side_effect=RuntimeError("boom")):
        assert series_location.place_added_series({"comicid": DIE, "root": str(library.collected)}) is None
    assert series_location.place_added_series({"comicid": DIE}) is None


def test_routes_answer_with_options_and_roots(library):
    _add_series(DIE, "Die", library.comics / "Image" / "Die")

    options = fork_router.get_series_folder_options(DIE, library.ctx)
    roots = fork_router.get_library_roots(library.ctx)
    missing = fork_router.get_series_folder_options("404", library.ctx)

    assert options["options"][0]["automatic"] is True
    assert roots["comic_default"] == str(library.comics)
    assert roots["manga_default"] == str(library.manga)
    assert missing.status_code == 404
    assert json.loads(missing.body)["detail"].startswith("Series 404")

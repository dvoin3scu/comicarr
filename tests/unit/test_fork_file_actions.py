#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Fork: rename a Series' files to its naming format, and name manga imports."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import comicarr
from comicarr import db
from comicarr.app.imports import finalization
from comicarr.app.series import file_actions, fork_router
from comicarr.db import get_engine, shutdown_engine
from comicarr.tables import metadata

DANDADAN = "145549"
DIE = "117000"


@pytest.fixture
def library(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    root = tmp_path / "read"
    root.mkdir()
    config = SimpleNamespace(
        DESTINATION_DIR=str(root),
        MANGA_DESTINATION_DIR=None,
        MAGAZINE_DESTINATION_DIR=None,
        ADDITIONAL_LIBRARY_ROOTS="",
        MULTIPLE_DEST_DIRS=None,
        MANGA_FILE_FORMAT="$Series v$Volume",
        FILE_FORMAT="$Series $Issue ($Year)",
        ZERO_LEVEL=True,
        ZERO_LEVEL_N="00x",
        IMP_RENAME=True,
        ANNUALS_ON=False,
    )
    monkeypatch.setattr(comicarr, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(comicarr, "CONFIG", config, raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    shutdown_engine()
    metadata.create_all(get_engine())
    yield SimpleNamespace(root=root, config=config)
    shutdown_engine()


def _series(library, comic_id, name, content_type="comic"):
    folder = library.root / name
    folder.mkdir()
    db.upsert(
        "comics",
        {
            "ComicName": name,
            "ComicYear": "2022",
            "ComicPublisher": "Viz",
            "ComicLocation": str(folder),
            "ContentType": content_type,
            "ContentKindSetBy": "operator",
            "Status": "Active",
        },
        {"ComicID": comic_id},
    )
    return folder


def _issue(comic_id, issue_id, number, filename=None, folder=None):
    db.upsert(
        "issues",
        {
            "ComicID": comic_id,
            "Issue_Number": number,
            "Status": "Downloaded" if filename else "Wanted",
            "Location": filename,
        },
        {"IssueID": issue_id},
    )
    if filename and folder is not None:
        (folder / filename).write_text(issue_id)


def _dandadan(library):
    folder = _series(library, DANDADAN, "Dandadan", "manga")
    _issue(DANDADAN, "1", "1", "Dandadan 001 (2022).cbz", folder)
    _issue(DANDADAN, "2", "2", "Dandadan v002.cbz", folder)
    _issue(DANDADAN, "3", "3")
    return folder


def test_a_manga_series_is_previewed_with_the_manga_format(library):
    _dandadan(library)

    plan = file_actions.rename_plan(DANDADAN)

    assert plan["content_type"] == "manga"
    assert plan["to_rename"] == 1
    first, second = plan["items"]
    assert (first["current"], first["proposed"], first["status"]) == (
        "Dandadan 001 (2022).cbz",
        "Dandadan v001.cbz",
        "rename",
    )
    assert second["status"] == "unchanged"


def test_rename_moves_the_file_in_its_folder_and_repoints_the_issue(library):
    folder = _dandadan(library)

    result = file_actions.rename_files(DANDADAN)

    assert result == {
        "success": True,
        "renamed": 1,
        "conflicts": 0,
        "files": [{"issue_id": "1", "from": "Dandadan 001 (2022).cbz", "to": "Dandadan v001.cbz"}],
        "errors": [],
    }
    assert sorted(p.name for p in folder.iterdir()) == ["Dandadan v001.cbz", "Dandadan v002.cbz"]
    row = db.raw_select_one("SELECT Location FROM issues WHERE IssueID=?", ["1"])
    assert row["Location"] == "Dandadan v001.cbz"


def test_only_the_chosen_issues_are_renamed(library):
    folder = _dandadan(library)
    _issue(DANDADAN, "4", "4", "dandadan_04.cbz", folder)

    plan = file_actions.rename_plan(DANDADAN, ["4"])
    assert [item["issue_id"] for item in plan["items"]] == ["4"]

    file_actions.rename_files(DANDADAN, ["4"])
    assert (folder / "Dandadan v004.cbz").exists()
    assert (folder / "Dandadan 001 (2022).cbz").exists()


def test_a_name_already_taken_is_a_conflict_and_is_left_alone(library):
    folder = _dandadan(library)
    (folder / "Dandadan v001.cbz").write_text("someone else")

    plan = file_actions.rename_plan(DANDADAN)
    assert plan["conflicts"] == 1
    assert file_actions.rename_files(DANDADAN)["renamed"] == 0
    assert (folder / "Dandadan 001 (2022).cbz").read_text() == "1"


def test_a_comic_series_uses_the_comic_format(library):
    folder = _series(library, DIE, "Die")
    _issue(DIE, "11", "1", "die_01.cbz", folder)

    with patch("comicarr.helpers.rename_param", return_value={"nfilename": "Die 001 (2018).cbz"}) as rename:
        plan = file_actions.rename_plan(DIE)

    assert plan["content_type"] == "comic"
    assert plan["items"][0]["proposed"] == "Die 001 (2018).cbz"
    assert rename.call_args.kwargs["issueid"] == "11"


def test_a_name_the_format_cannot_build_is_kept(library):
    folder = _series(library, DIE, "Die")
    _issue(DIE, "11", "1", "die_01.cbz", folder)

    with patch("comicarr.helpers.rename_param", side_effect=NameError("ext")):
        assert file_actions.rename_plan(DIE)["items"][0]["status"] == "unchanged"


def test_routes_preview_rename_and_refuse_bad_input(library):
    _dandadan(library)

    preview = fork_router.preview_series_rename(DANDADAN, {})
    assert preview["to_rename"] == 1
    assert all("_path" not in item for item in preview["items"])
    assert fork_router.preview_series_rename(DANDADAN, {"issue_ids": "1"}).status_code == 400
    assert fork_router.preview_series_rename("404", None).status_code == 404

    with patch.object(comicarr, "APILOCK", SimpleNamespace(acquire=lambda blocking: False), create=True):
        busy = fork_router.rename_series_files(DANDADAN, {"issue_ids": ["1"]})
    assert busy.status_code == 409
    assert json.loads(busy.body)["detail"].startswith("Post-processing")


def test_an_inbox_import_into_a_manga_series_takes_the_manga_format(library):
    _dandadan(library)
    row = {"ComicLocation": "/inbox/DanDaDan_Vol05.cbz", "_ResolvedIssueID": None, "IssueNumber": "5"}
    db.upsert("issues", {"ComicID": DANDADAN, "Issue_Number": "5"}, {"IssueID": "5"})

    with patch("comicarr.helpers.rename_param") as comic_rename:
        path = finalization._destination_path(row, DANDADAN, "Dandadan", "/lib/Dandadan", library.config)
        resolved = finalization._destination_path(
            {**row, "_ResolvedIssueID": "5"}, DANDADAN, "Dandadan", "/lib/Dandadan", library.config
        )

        parsed = finalization._destination_path(
            {"ComicLocation": "/inbox/DanDaDan v06.cbz"}, DANDADAN, "Dandadan", "/lib/Dandadan", library.config
        )

    comic_rename.assert_not_called()
    assert path == "/lib/Dandadan/Dandadan v005.cbz"
    assert resolved == "/lib/Dandadan/Dandadan v005.cbz"
    assert parsed == "/lib/Dandadan/Dandadan v006.cbz"


def test_an_inbox_import_keeps_its_name_without_rename_or_a_manga_format(library):
    _dandadan(library)
    row = {"ComicLocation": "/inbox/DanDaDan_Vol05.cbz", "_ResolvedIssueID": None}

    library.config.MANGA_FILE_FORMAT = ""
    assert (
        finalization._destination_path(row, DANDADAN, "Dandadan", "/lib", library.config) == "/lib/DanDaDan_Vol05.cbz"
    )

    library.config.MANGA_FILE_FORMAT = "$Series v$Volume"
    library.config.IMP_RENAME = False
    assert (
        finalization._destination_path(row, DANDADAN, "Dandadan", "/lib", library.config) == "/lib/DanDaDan_Vol05.cbz"
    )


def test_an_inbox_import_into_a_comic_series_is_left_to_upstream(library):
    _series(library, DIE, "Die")
    assert file_actions.manga_import_file_name({}, DIE, "die.cbz", library.config) is None
    assert file_actions.manga_import_file_name({}, "404", "die.cbz", library.config) is None

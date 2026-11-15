#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Fork: downloaded manga volumes move with Change folder and take part in Rename."""

from types import SimpleNamespace

from comicarr import db
from comicarr.app.manga import volumes
from comicarr.app.series import file_actions
from comicarr.app.series import location as series_location
from comicarr.app.series import queries as series_queries
from tests.unit.test_fork_file_actions import DANDADAN, _dandadan, library  # noqa: F401


def _volume(folder, number, filename):
    (folder / filename).write_text("volume %s" % number)
    return volumes.record_volume(DANDADAN, number, volumes.DOWNLOADED, location=filename)


def _volume_location(volume_id):
    return db.raw_select_one("SELECT Location FROM manga_volumes WHERE VolumeID=?", [volume_id])["Location"]


def test_a_downloaded_volume_is_a_holding_of_its_series(library):  # noqa: F811
    folder = _dandadan(library)
    volume_id = _volume(folder, "4", "Dandadan v004.cbz")
    volumes.record_volume(DANDADAN, "5", volumes.SNATCHED)

    rows = series_queries.get_series_holdings(DANDADAN)

    assert {"table": "manga_volumes", "IssueID": volume_id, "Location": "Dandadan v004.cbz"} in rows
    assert [row for row in rows if row["table"] == "manga_volumes"] == [
        {"table": "manga_volumes", "IssueID": volume_id, "Location": "Dandadan v004.cbz"}
    ]


def test_change_folder_moves_volume_files_and_keeps_their_rows_pointing_at_them(library):  # noqa: F811
    folder = _dandadan(library)
    volume_id = _volume(folder, "4", "Dandadan v004.cbz")
    target = library.root / "manga" / "Dandadan"

    result = series_location.change_series_location(
        SimpleNamespace(config=library.config), DANDADAN, str(target), move_files=True
    )

    assert result["success"] is True
    assert (target / "Dandadan v004.cbz").is_file()
    assert not (folder / "Dandadan v004.cbz").exists()
    assert _volume_location(volume_id) == "Dandadan v004.cbz"


def test_rename_names_a_volume_file_from_its_volume_number(library):  # noqa: F811
    folder = _dandadan(library)
    volume_id = _volume(folder, "4", "Dandadan Vol. 4 (Digital).cbz")

    plan = file_actions.rename_plan(DANDADAN)
    item = next(item for item in plan["items"] if item["issue_id"] == volume_id)
    assert (item["proposed"], item["number"], item["status"]) == ("Dandadan v004.cbz", "4", "rename")

    file_actions.rename_files(DANDADAN)

    assert (folder / "Dandadan v004.cbz").is_file()
    assert _volume_location(volume_id) == "Dandadan v004.cbz"

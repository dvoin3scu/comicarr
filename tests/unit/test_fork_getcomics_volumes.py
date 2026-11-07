#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Fork: older GetComics pages that list one Main Server link per volume."""

import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup

import comicarr
from comicarr import getcomics

PAGE = Path(__file__).resolve().parents[1] / "fixtures" / "getcomics" / "grass-kings-volume-list.html"


def _soup():
    return BeautifulSoup(PAGE.read_text(encoding="utf-8"), "html.parser")


def test_each_volume_gives_its_main_server_link():
    links = getcomics.volume_list_links(_soup(), pack=True)

    assert [(link["series"], link["issues"], link["year"], link["size"]) for link in links] == [
        ("Grass Kings", "1", "2018", "322 MB"),
        ("Grass Kings", "2", "2018", "273 MB"),
        ("Grass Kings", "3", "2018", "284 MB"),
    ]
    assert all(link["site"] == "Main Server" for link in links)
    assert all(link["links"].startswith("https://getcomics.org/dls/") for link in links)
    assert getcomics.volume_links_name(links) == "Grass Kings (2018)"


def test_only_the_volumes_inside_the_pack_range_are_kept():
    packinfo = {"pack_issuelist": {"issue_range": ["2", 3]}}
    links = getcomics.volume_list_links(_soup(), packinfo)
    assert [link["issues"] for link in links] == ["2", "3"]


def test_a_page_without_a_volume_list_gives_nothing():
    html = "<ul><li><a href='https://getcomics.org/dls/x'>Main Server</a></li><li>Grass Kings (2018)</li></ul>"
    assert getcomics.volume_list_links(BeautifulSoup(html, "html.parser")) == []


def test_the_grab_queues_every_volume_when_no_download_button_is_found(tmp_path, monkeypatch):
    cache = tmp_path / "html_cache"
    cache.mkdir()
    shutil.copy(PAGE, cache / "getcomics-117629.html")
    monkeypatch.setattr(comicarr, "CONFIG", SimpleNamespace(CACHE_DIR=str(tmp_path)), raising=False)
    gc = getcomics.GC.__new__(getcomics.GC)

    with (
        patch.object(getcomics.GC, "loadsite"),
        patch.object(getcomics.GC, "_queue_download_batch", return_value={"success": True}) as queue,
    ):
        result = gc.parse_downloadresults(
            "117629", "https://getcomics.org/x", comicinfo=[{"booktype": "TPB", "pack": True}]
        )

    assert result == {"success": True}
    item_id, mainlink, links, filename, *_ = queue.call_args.args
    assert item_id == "117629"
    assert filename == "Grass Kings (2018)"
    assert [link["issues"] for link in links] == ["1", "2", "3"]


def test_a_retry_after_a_failed_link_does_not_queue_the_volumes_again(tmp_path, monkeypatch):
    cache = tmp_path / "html_cache"
    cache.mkdir()
    shutil.copy(PAGE, cache / "getcomics-117629-1.html")
    monkeypatch.setattr(comicarr, "CONFIG", SimpleNamespace(CACHE_DIR=str(tmp_path)), raising=False)
    gc = getcomics.GC.__new__(getcomics.GC)

    with patch.object(getcomics.GC, "loadsite"), patch.object(getcomics.GC, "_queue_download_batch") as queue:
        result = gc.parse_downloadresults(
            "117629-1", "https://getcomics.org/x", comicinfo=[{"booktype": "TPB"}], link_type_failure=["GC-Main"]
        )

    queue.assert_not_called()
    assert result == {"success": False, "links_exhausted": ["GC-Main"]}

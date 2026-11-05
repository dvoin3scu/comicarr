#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Manga folder and file naming (MANGA_FOLDER_FORMAT, MANGA_VOLUME/CHAPTER_FORMAT)."""

import os
from types import SimpleNamespace

import pytest

import comicarr
from comicarr.app.manga import naming
from comicarr.app.series import service as series_service
from comicarr.postprocessor import PostProcessor

# --- folders -----------------------------------------------------------------


def test_folder_format_makes_subfolders_from_author_year_series():
    assert (
        naming.render_folder("$Author/[$Year] $Series", series="Gunnm", year="1990", author="Yukito Kishiro")
        == "Yukito Kishiro/[1990] Gunnm"
    )


def test_publisher_token_means_author_for_manga():
    # A shared comic FOLDER_FORMAT used to leave "$Publisher" in the folder name
    # and turn "/" into "-": "$Publisher-[1990] Gunnm".
    assert (
        naming.render_folder("$Publisher/[$Year] $Series", series="Gunnm", year="1990", author="Yukito Kishiro")
        == "Yukito Kishiro/[1990] Gunnm"
    )


@pytest.mark.parametrize("year", [None, "", "0000", "None"])
def test_missing_year_leaves_no_empty_brackets(year):
    assert naming.render_folder("$Author/[$Year] $Series", series="Gunnm", year=year, author="Yukito Kishiro") == (
        "Yukito Kishiro/Gunnm"
    )


def test_missing_author_drops_the_empty_level():
    assert naming.render_folder("$Author/$Series ($Year)", series="Berserk", year="1989", author=None) == (
        "Berserk (1989)"
    )


def test_each_part_is_filesafe_and_cannot_escape():
    assert naming.render_folder("$Author/../$Series", series="Batman: Year One?", author="A/B") == (
        "A-B/Batman Year One"
    )


@pytest.mark.parametrize("fmt", [None, "", "   "])
def test_empty_format_returns_none(fmt):
    assert naming.render_folder(fmt, series="Gunnm", year="1990", author="Yukito Kishiro") is None


def test_manga_series_location_uses_manga_folder_format(monkeypatch):
    monkeypatch.setattr(comicarr, "CONFIG", SimpleNamespace(MANGA_FOLDER_FORMAT="$Author/[$Year] $Series"))
    assert series_service.manga_series_location("Gunnm", "/manga", year="1990", author="Yukito Kishiro") == (
        os.path.join("/manga", "Yukito Kishiro", "[1990] Gunnm")
    )


def test_manga_series_location_without_format_keeps_legacy_folder(monkeypatch):
    monkeypatch.setattr(comicarr, "CONFIG", SimpleNamespace(MANGA_FOLDER_FORMAT=""))
    assert series_service.manga_series_location("Gunnm", "/manga", year="1990", author="Yukito Kishiro") == (
        os.path.join("/manga", "Gunnm")
    )


def test_reclassify_passes_year_and_author(monkeypatch):
    monkeypatch.setattr(comicarr, "CONFIG", SimpleNamespace(MANGA_FOLDER_FORMAT="$Author/[$Year] $Series"))
    new_location, _warning = series_service.manga_location_for_reclassify(
        {
            "ComicID": "md-1",
            "ComicName": "Gunnm",
            "ComicYear": "1990",
            "ComicPublisher": "Yukito Kishiro",
            "ComicLocation": "/comics/Gunnm (1990)",
        },
        "/manga",
    )
    assert new_location == os.path.join("/manga", "Yukito Kishiro", "[1990] Gunnm")


# --- files -------------------------------------------------------------------


def _stem(filename, parsed, **kwargs):
    defaults = {
        "series": "Gunnm",
        "year": "1990",
        "author": "Yukito Kishiro",
        "file_format": "$Series v$Volume c$Chapter",
        "zero_level": True,
        "zero_level_n": "00x",
    }
    defaults.update(kwargs)
    return naming.render_file_stem(filename=filename, parsed=parsed, **defaults)


def test_volume_file_drops_the_empty_chapter_with_its_marker():
    assert _stem("Gunnm_Vol01_[Group]", {"volume_number": 1, "chapter_number": None}) == "Gunnm v001"


def test_chapter_file_drops_the_empty_volume_and_keeps_decimals():
    assert _stem("Gunnm - Ch 10.5", {"volume_number": None, "chapter_number": 10.5}) == "Gunnm c010.5"


def test_file_with_both_numbers_gets_both():
    assert _stem("Gunnm v02 c012", {"volume_number": 2, "chapter_number": 12.0}) == "Gunnm v002 c012"


@pytest.mark.parametrize(
    ("fmt", "expected"),
    [
        ("$Series Vol. $Volume Ch. $Chapter", "Gunnm Ch. 012"),
        ("$Series - Volume $Volume - Chapter $Chapter", "Gunnm - Chapter 012"),
        ("$Series_v$Volume_c$Chapter", "Gunnm_c012"),
        ("$Series #$Volume ($Chapter)", "Gunnm (012)"),
        ("[$Author] $Series v$Volume c$Chapter", "[Yukito Kishiro] Gunnm c012"),
    ],
)
def test_empty_token_and_marker_are_dropped_in_any_style(fmt, expected):
    assert _stem("Gunnm c012", {"volume_number": None, "chapter_number": 12.0}, file_format=fmt) == expected


@pytest.mark.parametrize(
    ("name", "parsed", "expected"),
    [
        ("Gunnm_Vol01-03_[Group]", {"volume_number": 1}, "Gunnm v001-003"),
        ("Gunnm Vol. 1 - 3", {"volume_number": 1}, "Gunnm v001-003"),
        ("Gunnm v01 - v03", {"volume_number": 1}, "Gunnm v001-003"),
        ("Gunnm c001-010", {"chapter_number": 1.0}, "Gunnm c001-010"),
        ("Gunnm c10~12.5", {"chapter_number": 10.0}, "Gunnm c010-012.5"),
        ("Gunnm v02 c010-012", {"volume_number": 2, "chapter_number": 10.0}, "Gunnm v002 c010-012"),
    ],
)
def test_range_releases_name_both_ends(name, parsed, expected):
    assert _stem(name, parsed) == expected


@pytest.mark.parametrize("name", ["Gunnm v03-01", "Gunnm v01-03 c001-020"])
def test_odd_ranges_keep_their_name(name):
    assert _stem(name, {"volume_number": 1, "chapter_number": 1.0}) is None


def test_no_number_keeps_the_name():
    assert _stem("Gunnm Extras", {"volume_number": None, "chapter_number": None}) is None


@pytest.mark.parametrize("fmt", [None, "", "   "])
def test_no_format_keeps_the_name(fmt):
    assert _stem("Gunnm v01", {"volume_number": 1, "chapter_number": None}, file_format=fmt) is None


def test_padding_off():
    assert _stem("Gunnm v01", {"volume_number": 1, "chapter_number": None}, zero_level=False) == "Gunnm v1"


def test_unparsed_file_keeps_its_name():
    assert _stem("whatever", None) is None


def test_postprocessor_target_name(monkeypatch):
    monkeypatch.setattr(
        comicarr,
        "CONFIG",
        SimpleNamespace(MANGA_FILE_FORMAT="$Series v$Volume c$Chapter", ZERO_LEVEL=True, ZERO_LEVEL_N="00x"),
    )
    pp = PostProcessor.__new__(PostProcessor)
    series = {"ComicName": "Gunnm", "ComicYear": "1990", "ComicPublisher": "Yukito Kishiro"}
    assert pp._manga_target_name("Gunnm_v01.CBZ", {"volume_number": 1}, series) == "Gunnm v001.cbz"
    assert pp._manga_target_name("Gunnm v001.cbz", {"volume_number": 1}, series) is None


def test_postprocessor_target_name_off_by_default(monkeypatch):
    monkeypatch.setattr(comicarr, "CONFIG", SimpleNamespace(MANGA_FILE_FORMAT=""))
    pp = PostProcessor.__new__(PostProcessor)
    assert pp._manga_target_name("Gunnm_v01.cbz", {"volume_number": 1}, {"ComicName": "Gunnm"}) is None


def test_non_string_format_is_ignored():
    assert naming.render_folder(object(), series="Gunnm") is None


def test_trailing_empty_chapter_takes_its_separator():
    fmt = "$Series - v$Volume - c$Chapter"
    assert _stem("Gunnm v01", {"volume_number": 1, "chapter_number": None}, file_format=fmt) == "Gunnm - v001"

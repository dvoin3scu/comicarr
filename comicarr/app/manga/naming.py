#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Folder and file names for manga Series.

Manga metadata (MangaDex, MyAnimeList) has no English publisher: the Series'
``ComicPublisher`` holds the author, and ``ComicYear`` the original start year.
So manga gets its own formats, with ``$Author`` as the natural top level:

- ``MANGA_FOLDER_FORMAT`` (e.g. ``$Author/[$Year] $Series``): ``/`` makes
  subfolders, each part is made filesafe on its own.
- ``MANGA_FILE_FORMAT`` (e.g. ``$Series v$Volume c$Chapter``): the name a
  downloaded file is given. Like ``$Annual`` for comics, a token the file has
  no number for is dropped together with the marker written against it, so a
  volume becomes ``Gunnm v001`` and a chapter ``Gunnm c010.5``.

Empty formats keep the existing behaviour, so nothing changes until an
operator opts in. These functions are pure: callers pass the config values.
"""

import re

from comicarr.app.common.strings import filesafe
from comicarr.app.manga.ledger import normalize_volume_number

_EMPTY_YEARS = frozenset({"", "0", "0000", "none", "null", "unknown"})
# A volume or chapter range in a release name, with its kind and both ends:
# "v01-03", "_Vol01-03_", "c001 - c010", "Vol. 1 - 3". The lookbehind (not \b)
# lets "_" sit before the marker, as in "Gunnm_Vol01-03".
_MARK = r"(?:v(?:ol(?:ume)?)?|c(?:h(?:apter)?)?)"
_RANGE_PARTS = re.compile(
    r"(?<![a-z])(?P<kind>" + _MARK + r")\.?\s*(?P<first>\d+(?:\.\d+)?)"
    r"\s*[-~–]\s*(?:" + _MARK + r"\.?\s*)?(?P<last>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_EMPTY_BRACKETS = re.compile(r"\(\s*\)|\[\s*\]|\{\s*\}")
_SPACES = re.compile(r"\s+")


def _text(value):
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in ("none", "null") else text


def _year(value):
    text = _text(value)
    return "" if text.lower() in _EMPTY_YEARS else text


def _replace(fmt, values):
    # Longest token first, so $Series never eats part of a longer token.
    for token in sorted(values, key=len, reverse=True):
        fmt = fmt.replace(token, values[token])
    return fmt


def _tidy(part):
    part = _EMPTY_BRACKETS.sub("", part)
    part = _SPACES.sub(" ", part)
    return part.strip(" -_.")


def _folder_values(series, year, author):
    series, year, author = _text(series), _year(year), _text(author)
    return {
        "$Series": series,
        "$series": series.lower(),
        "$Year": year,
        "$Author": author,
        "$author": author.lower(),
        # Comic-only tokens a shared FOLDER_FORMAT may carry. For manga the
        # publisher slot is the author (that is what the Series stores).
        "$Publisher": author,
        "$publisher": author.lower(),
        "$Imprint": "",
        "$VolumeY": ("V" + year) if year else "",
        "$VolumeN": "",
        "$Type": "",
    }


def render_folder(fmt, *, series, year=None, author=None):
    """Relative folder (parts joined by ``/``) for a manga Series, or None.

    Each ``/``-separated part is filled, made filesafe and tidied on its own;
    parts that end up empty (an unknown author, say) are dropped rather than
    leaving an empty path level. None when the format or the series name is
    empty, so callers fall back to their old behaviour.
    """
    fmt = _text(fmt) if isinstance(fmt, str) else ""
    if not fmt or not _text(series):
        return None
    values = _folder_values(series, year, author)
    parts = []
    for raw in fmt.replace("\\", "/").split("/"):
        part = _tidy(filesafe(_tidy(_replace(raw, values))))
        if part and part not in (".", ".."):
            parts.append(part)
    if not parts:
        return None
    return "/".join(parts)


def is_range_release(filename):
    """Does this release name cover a run of volumes or chapters?"""
    return bool(_RANGE_PARTS.search(_text(filename)))


def _pad(number, zero_level, zero_level_n):
    """Zero-pad the integer part the way comic issue numbers are padded."""
    text = _text(number)
    if not text or not zero_level:
        return text
    width = {"0x": 2, "00x": 3}.get(_text(zero_level_n))
    if not width:
        return text
    whole, dot, frac = text.partition(".")
    if not whole.isdigit():
        return text
    return whole.zfill(width) + dot + frac


def _chapter_text(value):
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _text(value)
    return str(int(number)) if number.is_integer() else format(number, "g")


def _range(filename, zero_level, zero_level_n):
    """("volume" | "chapter", "001-003") for a range release, or None.

    None when the name holds more than one range, or the run does not go up
    (``v03-01``), so an odd name keeps its release name.
    """
    matches = list(_RANGE_PARTS.finditer(_text(filename)))
    if len(matches) != 1:
        return None
    match = matches[0]
    first, last = float(match.group("first")), float(match.group("last"))
    if last <= first:
        return None
    kind = "volume" if match.group("kind")[0].lower() == "v" else "chapter"
    span = "-".join(_pad(_chapter_text(n), zero_level, zero_level_n) for n in (first, last))
    return kind, span


def _drop_empty(fmt, values):
    """Remove each empty number token with the marker written against it.

    The marker is a short word right before the token, after a space, bracket
    or separator (``v$Volume``, ``Vol. $Volume``, ``_c$Chapter``, ``#$Volume``),
    so ``$Series v$Volume c$Chapter`` on a chapter file is ``$Series c$Chapter``.
    """
    for token in ("$Volume", "$Chapter"):
        if not values.get(token):
            # The separator run before it goes too, so " - Volume $Volume" or
            # "_v$Volume" leaves no doubled " - - " or "__" behind.
            marker = r"[\s_\-]*(?:(?<=[\s\[\](){}_\-])|^)(?:[A-Za-z]{1,8}\.?\s?|#)?"
            fmt = re.sub(marker + re.escape(token), "", fmt)
    return fmt


def render_file_stem(
    *,
    filename,
    parsed,
    series,
    year=None,
    author=None,
    file_format=None,
    zero_level=False,
    zero_level_n=None,
):
    """New file name (without extension) for a manga file, or None to keep it.

    ``$Volume`` and ``$Chapter`` are filled from what the file carries, and an
    empty one is dropped with its marker (see :func:`_drop_empty`). A range
    release fills its token with both ends, so ``Gunnm_Vol01-03`` becomes
    ``Gunnm v001-003``; a name with more than one range keeps its release name,
    and so does a file with neither number.
    """
    if not parsed or not _text(file_format):
        return None
    chapter = parsed.get("chapter_number")
    volume = parsed.get("volume_number")
    volume_text = _pad(normalize_volume_number(volume) or "", zero_level, zero_level_n) if volume is not None else ""
    chapter_text = _pad(_chapter_text(chapter), zero_level, zero_level_n) if chapter is not None else ""
    if is_range_release(filename):
        found = _range(filename, zero_level, zero_level_n)
        if found is None:
            return None
        kind, span = found
        if kind == "volume":
            volume_text, chapter_text = span, ""
        else:
            chapter_text = span
    if not volume_text and not chapter_text:
        return None
    values = {
        "$Series": _text(series),
        "$series": _text(series).lower(),
        "$Year": _year(year),
        "$Author": _text(author),
        "$author": _text(author).lower(),
        "$Volume": volume_text,
        "$Chapter": chapter_text,
    }
    fmt = _drop_empty(_text(file_format).replace("/", " "), values)
    stem = _tidy(filesafe(_tidy(_replace(fmt, values))))
    return stem or None

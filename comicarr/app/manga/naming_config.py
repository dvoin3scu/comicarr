#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""The manga naming formats applied with the running configuration.

``naming`` stays pure; this module reads ``MANGA_FOLDER_FORMAT``,
``MANGA_FILE_FORMAT`` and the padding settings from ``comicarr.CONFIG`` so the
add, location and post-processing code each make a single call.
"""

import os

import comicarr
from comicarr import logger
from comicarr.app.common.strings import filesafe
from comicarr.app.manga import naming


def _config(name, default=None):
    return getattr(getattr(comicarr, "CONFIG", None), name, default)


def _text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def series_folder(dest, series, *, year=None, author=None, fallback_format=None):
    """The automatic folder for a manga Series under ``dest``, or None.

    ``MANGA_FOLDER_FORMAT`` decides it when set, else ``fallback_format``; with
    neither (or a format that renders nothing) it is ``<dest>/<filesafe(series)>``.
    Each "/" in the rendered format is a real subfolder.
    """
    dest = _text(dest)
    if not dest:
        return None
    fmt = _config("MANGA_FOLDER_FORMAT") or fallback_format
    relative = naming.render_folder(fmt, series=series, year=year, author=author)
    if relative:
        return os.path.join(dest, *relative.split("/"))
    folder = _text(filesafe(series)) if series else None
    return os.path.join(dest, folder) if folder else None


def placed_file_name(filename, parsed, series, module=""):
    """The ``MANGA_FILE_FORMAT`` name for a placed manga file, or None to keep it."""
    file_format = _config("MANGA_FILE_FORMAT")
    # Only a real string is a format: an unset or non-string value keeps the name.
    if not isinstance(file_format, str) or not file_format.strip():
        return None
    stem, ext = os.path.splitext(filename)
    new_stem = naming.render_file_stem(
        filename=stem,
        parsed=parsed,
        series=(series or {}).get("ComicName"),
        year=(series or {}).get("ComicYear"),
        author=(series or {}).get("ComicPublisher"),
        file_format=file_format,
        zero_level=_config("ZERO_LEVEL", False),
        zero_level_n=_config("ZERO_LEVEL_N"),
    )
    if not new_stem or new_stem == stem:
        return None
    renamed = new_stem + ext.lower()
    logger.fdebug("%s Renaming manga file: %s -> %s" % (module, filename, renamed))
    return renamed

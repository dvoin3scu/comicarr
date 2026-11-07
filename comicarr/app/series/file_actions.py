#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Fork: give a Series' files the name its current naming format asks for.

A comic Series uses ``FILE_FORMAT`` (the same ``rename_param`` post-processing
uses); a manga Series uses ``MANGA_FILE_FORMAT``. Files are renamed in the
folder they are in; nothing moves between folders. The same manga naming
applies to an Inbox import, which otherwise takes the comic format.
"""

import os

from comicarr import db, logger, series_kind
from comicarr.app.manga import naming_config as manga_naming
from comicarr.app.series import location as series_location
from comicarr.app.series import queries as series_queries

RENAME = "rename"
UNCHANGED = "unchanged"
CONFLICT = "conflict"


class FileActionError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _series(comic_id):
    return db.raw_select_one("SELECT * FROM comics WHERE ComicID=?", [comic_id])


def _issue_row(table, issue_id):
    return db.raw_select_one("SELECT * FROM %s WHERE IssueID=?" % table, [issue_id]) or {}


def _manga_numbers(row):
    """``parsed`` for the manga file stem, read from the issue row.

    A chapter keeps its number. A ComicVine manga keeps the volume in
    ``Issue_Number``, the same reading ``cmtag.manga_volume_for_issue`` uses.
    """
    chapter = row.get("ChapterNumber")
    volume = row.get("VolumeNumber")
    if chapter in (None, "") and volume in (None, ""):
        volume = row.get("Issue_Number")
    return {"chapter_number": chapter or None, "volume_number": volume or None}


def _comic_file_name(series, table, row, current_name):
    from comicarr import helpers

    renamed = helpers.rename_param(
        series["ComicID"],
        series.get("ComicName"),
        row.get("Issue_Number"),
        current_name,
        issueid=row.get("IssueID"),
        annualize="yes" if table == "annuals" else None,
    )
    return (renamed or {}).get("nfilename") or None


def target_file_name(series, table, row, current_name):
    """The name the current format gives this file, or None to keep it."""
    if series_kind.is_manga(series):
        return manga_naming.placed_file_name(current_name, _manga_numbers(row), series, "[RENAME]")
    return _comic_file_name(series, table, row, current_name)


def _holdings(comic_id, series, issue_ids):
    wanted = {str(issue_id) for issue_id in issue_ids} if issue_ids is not None else None
    retained = series_location.retained_locations(series)
    held = []
    for holding in series_location._held_files(comic_id, series.get("ComicLocation"), retained):
        if wanted is None or str(holding.issue_id) in wanted:
            held.append(holding)
    return held


def rename_plan(comic_id, issue_ids=None):
    """What a rename would do, file by file. Changes nothing."""
    series = _series(comic_id)
    if not series:
        raise FileActionError("Series %s is not in the library." % comic_id, status=404)
    items = []
    taken = set()
    for holding in _holdings(comic_id, series, issue_ids):
        row = _issue_row(holding.table, holding.issue_id)
        current = os.path.basename(holding.path)
        try:
            proposed = target_file_name(series, holding.table, row, current) or current
        except Exception as e:  # A file the format cannot name keeps its name.
            logger.fdebug("[RENAME] Could not name %s: %s" % (holding.path, e))
            proposed = current
        destination = os.path.join(os.path.dirname(holding.path), proposed)
        if proposed == current:
            status = UNCHANGED
        elif destination in taken or (os.path.lexists(destination) and os.path.realpath(destination) != holding.path):
            status = CONFLICT
        else:
            status = RENAME
        taken.add(destination)
        items.append(
            {
                "issue_id": holding.issue_id,
                "table": holding.table,
                "number": row.get("Issue_Number"),
                "folder": os.path.dirname(holding.path),
                "current": current,
                "proposed": proposed,
                "status": status,
                "_path": holding.path,
            }
        )
    items.sort(key=lambda item: (item["status"] == UNCHANGED, item["current"].lower()))
    return {
        "content_type": "manga" if series_kind.is_manga(series) else "comic",
        "items": items,
        "to_rename": sum(1 for item in items if item["status"] == RENAME),
        "conflicts": sum(1 for item in items if item["status"] == CONFLICT),
    }


def public_plan(plan):
    return {**plan, "items": [{k: v for k, v in item.items() if not k.startswith("_")} for item in plan["items"]]}


def _stored_location(old_location, new_path):
    if old_location and os.path.isabs(old_location):
        return new_path
    return os.path.basename(new_path)


def rename_files(comic_id, issue_ids=None):
    """Rename each file whose name differs from its format. Stops at the first failure."""
    renamed, errors = [], []
    with series_location._library_writes_paused():
        plan = rename_plan(comic_id, issue_ids)
        stored = {
            (row["table"], str(row["IssueID"])): row["Location"] for row in series_queries.get_series_holdings(comic_id)
        }
        for item in plan["items"]:
            if item["status"] != RENAME:
                continue
            source = item["_path"]
            destination = os.path.join(item["folder"], item["proposed"])
            try:
                os.rename(source, destination)
            except OSError as e:
                logger.error("[RENAME] Could not rename %s to %s: %s" % (source, item["proposed"], e))
                errors.append("Could not rename %s. The log has the reason." % item["current"])
                break
            old = stored.get((item["table"], str(item["issue_id"])))
            series_queries.set_holding_location(item["table"], item["issue_id"], _stored_location(old, destination))
            renamed.append({"issue_id": item["issue_id"], "from": item["current"], "to": item["proposed"]})
            logger.info("[RENAME] %s -> %s" % (item["current"], item["proposed"]))
    return {
        "success": not errors,
        "renamed": len(renamed),
        "conflicts": plan["conflicts"],
        "files": renamed,
        "errors": errors,
    }


def manga_import_file_name(row, series_id, original_filename, config):
    """The Inbox import name for a manga Series, or None for a comic one.

    With ``IMP_RENAME`` on, a manga Series takes ``MANGA_FILE_FORMAT`` and never
    the comic ``FILE_FORMAT``; with no manga format the file keeps its name.
    """
    try:
        series = _series(series_id)
        if not series or not series_kind.is_manga(series):
            return None
    except Exception as e:
        logger.fdebug("[IMPORT-MATCH] Could not read Series %s: %s" % (series_id, e))
        return None
    try:
        if not getattr(config, "IMP_RENAME", False):
            return original_filename
        issue_id = row.get("_ResolvedIssueID")
        if issue_id:
            parsed = _manga_numbers(_issue_row("issues", issue_id))
        else:
            from comicarr.app.manga.parse import parse_in_series_context

            parsed = parse_in_series_context(original_filename, series=series, series_name=series.get("ComicName"))
            if not parsed:
                parsed = _manga_numbers({"Issue_Number": row.get("IssueNumber")})
        return manga_naming.placed_file_name(original_filename, parsed, series, "[IMPORT-MATCH]") or original_filename
    except Exception as e:
        logger.fdebug("[IMPORT-MATCH] Manga naming skipped for %s: %s" % (original_filename, e))
        return original_filename

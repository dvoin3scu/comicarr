#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""The ComicInfo ``<SeriesGroup>`` a Series' files are tagged with (fork).

ComicVine catalogues each trade paperback, hardcover or omnibus as its own
Series ("Die: Fantasy Heartbreaker", "Die: Split the Party"), so a reader sees
them apart from the single issues they collect. ``<SeriesGroup>`` names the
family they belong to; Kavita turns it into a Collection, other readers group
on it too.

The group is worked out, in order:

1. the operator's choice for this Series (which may be "no group");
2. the Series a collected edition collects, from ComicVine's "Collects ..."
   description (stored in ``comics.Collects``);
3. for a collected edition, the part of its name before the first colon;
4. for any Series, its own name when another Series in the library names it as
   their group, so the single issues join the collected editions.

Operator choices live in ``series_groups.json`` next to the database rather than
in a new column: a database migration would tie the database to this fork.
"""

import json
import os
import re
import tempfile
import threading

from sqlalchemy import select

import comicarr
from comicarr import db, logger
from comicarr.tables import comics

COLLECTED_TYPES = frozenset({"TPB", "HC", "GN", "OMNIBUS"})
FILE_NAME = "series_groups.json"

SOURCE_CHOSEN = "chosen"
SOURCE_NONE_CHOSEN = "none"
SOURCE_COLLECTS = "collects"
SOURCE_NAME = "name"
SOURCE_PARENT = "parent"

_lock = threading.Lock()


def _store_path():
    base = getattr(comicarr, "DATA_DIR", None)
    if not base:
        return None
    return os.path.join(base, FILE_NAME)


def load_choices():
    """Return ``{ComicID: group}``; an empty string means "no group"."""
    path = _store_path()
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError) as e:
        logger.warn("[SERIES-GROUP] Ignoring unreadable %s: %s" % (path, e))
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): value.strip() for key, value in raw.items() if isinstance(value, str)}


def _write_choices(choices):
    path = _store_path()
    if not path:
        raise RuntimeError("Comicarr has no data folder to save the series group in.")
    folder = os.path.dirname(path)
    handle, temp = tempfile.mkstemp(prefix=".series_groups.", suffix=".json", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            json.dump(choices, out, indent=2, sort_keys=True, ensure_ascii=False)
        os.replace(temp, path)
    except Exception:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def set_choice(comic_id, value):
    """Record the operator's group: a name, "" for no group, or None for automatic."""
    comic_id = str(comic_id)
    with _lock:
        choices = load_choices()
        if value is None:
            choices.pop(comic_id, None)
        else:
            choices[comic_id] = clean_group(value) or ""
        _write_choices(choices)


def clean_group(value):
    if not isinstance(value, str):
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def _key(value):
    return (clean_group(value) or "").casefold()


def _bare_id(value):
    if value is None:
        return None
    value = str(value).strip()
    if value.startswith("4050-"):
        value = value[5:]
    return value or None


def _collects(row):
    raw = row.get("Collects")
    if not raw or raw == "None":
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


def _book_type(row):
    for key in ("Corrected_Type", "Type"):
        value = row.get(key)
        if isinstance(value, str) and value.strip() and value.strip().lower() != "none":
            return value.strip().upper()
    return None


def _from_collects(row, names_by_id):
    for entry in _collects(row):
        parent_id = _bare_id(entry.get("comicid"))
        if parent_id and parent_id != str(row.get("ComicID")) and parent_id in names_by_id:
            return clean_group(names_by_id[parent_id])
        name = clean_group(entry.get("series"))
        if name:
            return name
    return None


def _from_name(row):
    if _book_type(row) not in COLLECTED_TYPES:
        return None
    name = clean_group(row.get("ComicName"))
    if not name or ":" not in name:
        return None
    prefix = clean_group(name.split(":", 1)[0])
    if prefix and len(prefix) >= 2 and prefix.casefold() != name.casefold():
        return prefix
    return None


def _own_rule(row, names_by_id):
    """The group a Series gets from its own data alone (rules 2 and 3)."""
    group = _from_collects(row, names_by_id)
    if group:
        return group, SOURCE_COLLECTS
    group = _from_name(row)
    if group:
        return group, SOURCE_NAME
    return None, None


def _library_rows():
    return db.select_all(
        select(
            comics.c.ComicID,
            comics.c.ComicName,
            comics.c.Type,
            comics.c.Corrected_Type,
            comics.c.Collects,
        )
    )


def resolve_all(rows=None, choices=None):
    """Return ``{ComicID: (group or None, source or None)}`` for the whole library."""
    rows = [dict(row) for row in (rows if rows is not None else _library_rows())]
    choices = load_choices() if choices is None else choices
    names_by_id = {str(row["ComicID"]): row.get("ComicName") for row in rows}

    resolved = {}
    claimed_names = set()
    claimed_ids = set()
    for row in rows:
        comic_id = str(row["ComicID"])
        if comic_id in choices:
            chosen = clean_group(choices[comic_id])
            resolved[comic_id] = (chosen, SOURCE_CHOSEN) if chosen else (None, SOURCE_NONE_CHOSEN)
        else:
            resolved[comic_id] = _own_rule(row, names_by_id)
        if resolved[comic_id][0]:
            claimed_names.add(_key(resolved[comic_id][0]))
        for entry in _collects(row):
            parent_id = _bare_id(entry.get("comicid"))
            if parent_id and parent_id != comic_id:
                claimed_ids.add(parent_id)

    for row in rows:
        comic_id = str(row["ComicID"])
        if resolved[comic_id][0] or resolved[comic_id][1] == SOURCE_NONE_CHOSEN:
            continue
        name = clean_group(row.get("ComicName"))
        if name and (comic_id in claimed_ids or _key(name) in claimed_names):
            resolved[comic_id] = (name, SOURCE_PARENT)
    return resolved


def resolve(comic_id):
    """Return ``{"value", "source", "chosen"}`` for one Series."""
    comic_id = str(comic_id)
    choices = load_choices()
    value, source = resolve_all(choices=choices).get(comic_id, (None, None))
    return {"value": value, "source": source, "chosen": comic_id in choices}


def group_for_tagging(comic_id):
    """The ``seriesGroup`` ComicTagger should write, "" to clear it, or None to leave it.

    An operator's "no group" clears whatever the file carries; an unknown group
    leaves the file's own value alone.
    """
    try:
        result = resolve(comic_id)
    except Exception as e:
        logger.fdebug("[SERIES-GROUP] Could not resolve the group for %s: %s" % (comic_id, e))
        return None
    if result["value"]:
        return result["value"]
    if result["source"] == SOURCE_NONE_CHOSEN:
        return ""
    return None

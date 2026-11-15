#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Fork: downloaded manga volumes are holdings too.

Since 0022_manga_volumes a placed volume file lives in ``manga_volumes``, not
in ``issues``. A Series' holdings (the files Change folder moves and Files ->
Rename renames) only read ``issues`` and ``annuals``, so a volume file stayed
behind in the old folder while its row was left pointing at the new one. This
module adds those rows, keyed by ``VolumeID`` in the ``IssueID`` slot, and
writes their ``Location`` back.
"""

from sqlalchemy import select, update

from comicarr.app.core import db
from comicarr.app.core.tables import manga_volumes

TABLE = "manga_volumes"


def holdings(comic_id):
    """Every volume row of a Series that names a file, shaped like an issue holding."""
    rows = db.select_all(
        select(manga_volumes.c.VolumeID, manga_volumes.c.Location).where(
            manga_volumes.c.ComicID == str(comic_id), manga_volumes.c.Location.isnot(None)
        )
    )
    return [{"table": TABLE, "IssueID": row["VolumeID"], "Location": row["Location"]} for row in rows or ()]


def volume_row(volume_id):
    """One volume row as a dict (``VolumeNumber`` for naming), or {}."""
    return db.select_one(select(manga_volumes).where(manga_volumes.c.VolumeID == str(volume_id))) or {}


def set_location(table, volume_id, location, conn=None):
    """Write a volume holding's Location. False (nothing written) for any other table."""
    if table != TABLE:
        return False
    stmt = update(manga_volumes).where(manga_volumes.c.VolumeID == str(volume_id)).values(Location=location)
    if conn is not None:
        conn.execute(stmt)
    else:
        with db.get_engine().begin() as owned:
            owned.execute(stmt)
    return True

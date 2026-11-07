#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Fork routes: library-root folder choices and the ComicInfo series group.

Kept apart from ``series/router.py`` so the fork touches upstream routes as
little as possible.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from comicarr.app.core.context import AppContext, get_context
from comicarr.app.core.security import require_session
from comicarr.app.series import location as series_locations
from comicarr.app.series import queries as series_queries
from comicarr.app.series import series_group

router = APIRouter(prefix="/api", tags=["series"])


@router.get("/series/{comic_id}/folder-options", dependencies=[Depends(require_session)])
def get_series_folder_options(comic_id: str, ctx: AppContext = Depends(get_context)):
    """The automatic folder and the same folder under each other library root."""
    try:
        return series_locations.folder_options(comic_id, getattr(ctx, "config", None))
    except series_locations.SeriesLocationError as e:
        return JSONResponse(status_code=e.status, content={"detail": e.detail})


@router.get("/library-roots", dependencies=[Depends(require_session)])
def get_library_roots(ctx: AppContext = Depends(get_context)):
    """Roots a new Series can be added under, with the automatic one for each kind."""
    config = getattr(ctx, "config", None)
    roots = series_locations.placement_roots(config)

    def default_for(*keys):
        for key in keys:
            match = series_locations.matching_placement_root(getattr(config, key, None), config)
            if match:
                return match
        return roots[0] if roots else None

    return {
        "roots": roots,
        "comic_default": default_for("DESTINATION_DIR"),
        "manga_default": default_for("MANGA_DESTINATION_DIR", "DESTINATION_DIR"),
    }


@router.get("/series/{comic_id}/series-group", dependencies=[Depends(require_session)])
def get_series_group(comic_id: str):
    """The group this Series' files are tagged with, and where it comes from."""
    if not series_queries.get_series_location(comic_id):
        return JSONResponse(status_code=404, content={"detail": "Series %s is not in the library." % comic_id})
    return series_group.resolve(comic_id)


@router.patch("/series/{comic_id}/series-group", dependencies=[Depends(require_session)])
def update_series_group(comic_id: str, request_body: dict = None):
    """Choose the group: a name, "" for no group, or null to work it out again."""
    if not isinstance(request_body, dict) or "value" not in request_body:
        return JSONResponse(
            status_code=400,
            content={"detail": 'Provide value: a group name, "" for no group, or null for automatic'},
        )
    value = request_body["value"]
    if value is not None and not isinstance(value, str):
        return JSONResponse(status_code=400, content={"detail": "value must be text or null"})
    if isinstance(value, str) and len(value) > 200:
        return JSONResponse(status_code=400, content={"detail": "value is longer than 200 characters"})
    if not series_queries.get_series_location(comic_id):
        return JSONResponse(status_code=404, content={"detail": "Series %s is not in the library." % comic_id})
    series_group.set_choice(comic_id, value)
    return series_group.resolve(comic_id)

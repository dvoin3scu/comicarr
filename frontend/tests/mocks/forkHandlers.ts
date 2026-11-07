/**
 * Fork: default MSW handlers for the library-root and series-group routes.
 * Empty answers keep the dialogs in their typed-folder fallback.
 */
import { http, HttpResponse } from "msw";

export const forkHandlers = [
  http.get("/api/series/:comicId/folder-options", () =>
    HttpResponse.json({
      automatic: null,
      current: null,
      override: false,
      options: [],
    }),
  ),
  http.get("/api/library-roots", () =>
    HttpResponse.json({ roots: [], comic_default: null, manga_default: null }),
  ),
  http.get("/api/series/:comicId/series-group", () =>
    HttpResponse.json({ value: null, source: null, chosen: false }),
  ),
];

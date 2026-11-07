/**
 * Fork: library-root choices in the add and folder dialogs, and the series
 * group panel.
 */
import { describe, expect, it } from "vitest";
import { waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { render, screen } from "../test-utils";
import SearchAddButton from "@/components/search/SearchAddButton";
import { SeriesFolder } from "@/components/series/SeriesFolder";
import { SeriesGroupPanel } from "@/components/series/SeriesGroupPanel";
import type { SearchResult } from "@/types";

const die = { comicid: "119531", id: "119531", name: "Die" } as SearchResult;

const roots = {
  roots: [
    "/data/read/comics",
    "/data/read/manga",
    "/data/read/comics-collected",
  ],
  comic_default: "/data/read/comics",
  manga_default: "/data/read/manga",
};

describe("Add to a library root", () => {
  function captureAdd() {
    const sent: unknown[] = [];
    server.use(
      http.get("/api/library-roots", () => HttpResponse.json(roots)),
      http.post("/api/search/add", async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json({ success: true, comicid: "119531" });
      }),
    );
    return sent;
  }

  it("offers the automatic root first and adds under another root", async () => {
    const sent = captureAdd();
    const user = userEvent.setup();
    render(<SearchAddButton comic={die} contentType="comic" />);

    await user.click(
      screen.getByRole("button", { name: "Add Die to a chosen folder" }),
    );
    const automatic = await screen.findByRole("radio", {
      name: /\/data\/read\/comics\/… Automatic folder/,
    });
    expect((automatic as HTMLInputElement).checked).toBe(true);

    await user.click(
      screen.getByRole("radio", { name: /\/data\/read\/comics-collected\/…/ }),
    );
    await user.click(screen.getByRole("button", { name: "Add comic" }));

    await waitFor(() =>
      expect(sent).toEqual([
        { id: "119531", root: "/data/read/comics-collected" },
      ]),
    );
  });

  it("adds to the automatic folder when its root stays selected", async () => {
    const sent = captureAdd();
    const user = userEvent.setup();
    render(<SearchAddButton comic={die} contentType="comic" />);

    await user.click(
      screen.getByRole("button", { name: "Add Die to a chosen folder" }),
    );
    await screen.findByRole("radio", { name: /Automatic folder/ });
    await user.click(screen.getByRole("button", { name: "Add comic" }));

    await waitFor(() => expect(sent).toEqual([{ id: "119531" }]));
  });
});

describe("Change folder to another root", () => {
  function serveOptions() {
    const sent: unknown[] = [];
    server.use(
      http.get("/api/series/119531/folder-options", () =>
        HttpResponse.json({
          automatic: "/data/read/comics/Image/Die",
          current: "/data/read/comics/Image/Die",
          override: false,
          options: [
            {
              root: "/data/read/comics",
              folder: "/data/read/comics/Image/Die",
              automatic: true,
            },
            {
              root: "/data/read/comics-collected",
              folder: "/data/read/comics-collected/Image/Die",
              automatic: false,
            },
          ],
        }),
      ),
      http.patch("/api/series/119531/location", async ({ request }) => {
        const body = (await request.json()) as { folder: string | null };
        sent.push(body);
        return HttpResponse.json({
          success: true,
          comic_location: body.folder ?? "/data/read/comics/Image/Die",
          previous_location: "/data/read/comics/Image/Die",
          override: body.folder !== null,
          files_moved: 0,
          files_left: 0,
          retained_locations: [],
        });
      }),
    );
    return sent;
  }

  it("selects the current folder and saves the same folder under another root", async () => {
    const sent = serveOptions();
    const user = userEvent.setup();
    render(
      <SeriesFolder
        comicId="119531"
        location="/data/read/comics/Image/Die"
        override={false}
        retained={[]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Change folder" }));
    const current = await screen.findByRole("radio", {
      name: /\/data\/read\/comics\/Image\/Die Automatic folder/,
    });
    expect((current as HTMLInputElement).checked).toBe(true);

    await user.click(
      screen.getByRole("radio", {
        name: /\/data\/read\/comics-collected\/Image\/Die/,
      }),
    );
    await user.click(screen.getByRole("radio", { name: /Move them/ }));
    await user.click(screen.getByRole("button", { name: "Save folder" }));

    await waitFor(() =>
      expect(sent).toEqual([
        {
          folder: "/data/read/comics-collected/Image/Die",
          move_files: true,
        },
      ]),
    );
  });

  it("returns to the automatic folder when that option is saved", async () => {
    const sent = serveOptions();
    const user = userEvent.setup();
    render(
      <SeriesFolder
        comicId="119531"
        location="/data/read/comics-collected/Image/Die"
        override
        retained={[]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Change folder" }));
    await user.click(
      await screen.findByRole("radio", { name: /Automatic folder/ }),
    );
    await user.click(screen.getByRole("button", { name: "Save folder" }));

    await waitFor(() =>
      expect(sent).toEqual([{ folder: null, move_files: false }]),
    );
  });
});

describe("SeriesGroupPanel", () => {
  it("shows the group and where it came from", async () => {
    server.use(
      http.get("/api/series/124800/series-group", () =>
        HttpResponse.json({ value: "Die", source: "collects", chosen: false }),
      ),
    );
    render(<SeriesGroupPanel comicId="124800" />);

    await waitFor(() =>
      expect(screen.getByTestId("series-group").textContent).toBe("Die"),
    );
    expect(screen.getByText("from Collects")).toBeTruthy();
  });

  it("saves a chosen name and starts a re-tag", async () => {
    const patched: unknown[] = [];
    const retagged: unknown[] = [];
    server.use(
      http.get("/api/series/124800/series-group", () =>
        HttpResponse.json({ value: null, source: null, chosen: false }),
      ),
      http.patch("/api/series/124800/series-group", async ({ request }) => {
        patched.push(await request.json());
        return HttpResponse.json({
          value: "Die",
          source: "chosen",
          chosen: true,
        });
      }),
      http.post("/api/metadata/metatag/group", async ({ request }) => {
        retagged.push(await request.json());
        return HttpResponse.json({ success: true });
      }),
    );
    const user = userEvent.setup();
    render(<SeriesGroupPanel comicId="124800" />);

    await user.click(
      await screen.findByRole("button", { name: /Change group/ }),
    );
    await user.click(screen.getByRole("radio", { name: "Use this name" }));
    await user.type(screen.getByLabelText("Group name"), "Die");
    await user.click(screen.getByRole("button", { name: "Save group" }));
    await waitFor(() => expect(patched).toEqual([{ value: "Die" }]));

    await user.click(screen.getByRole("button", { name: /Re-tag files/ }));
    await waitFor(() => expect(retagged).toEqual([{ comic_id: "124800" }]));
    expect(await screen.findByText("Re-tagging started")).toBeTruthy();
  });

  it("saves no group as an empty name", async () => {
    const patched: unknown[] = [];
    server.use(
      http.patch("/api/series/124800/series-group", async ({ request }) => {
        patched.push(await request.json());
        return HttpResponse.json({ value: null, source: "none", chosen: true });
      }),
    );
    const user = userEvent.setup();
    render(<SeriesGroupPanel comicId="124800" />);

    await user.click(
      await screen.findByRole("button", { name: /Change group/ }),
    );
    await user.click(screen.getByRole("radio", { name: /No group/ }));
    await user.click(screen.getByRole("button", { name: "Save group" }));

    await waitFor(() => expect(patched).toEqual([{ value: "" }]));
  });
});

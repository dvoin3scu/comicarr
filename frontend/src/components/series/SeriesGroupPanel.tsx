/**
 * Fork: the ComicInfo <SeriesGroup> this series' files are tagged with, so a
 * reader can collect the single issues, trade paperbacks and omnibuses of one
 * story together. Lets the operator choose it and re-tag the files.
 */
import { useState } from "react";
import { LoaderCircle, Tags } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import {
  useRetagSeries,
  useSeriesGroup,
  useUpdateSeriesGroup,
  type SeriesGroup,
} from "@/hooks/useSeriesPlacement";
import { ApiError } from "@/lib/api";

type Mode = "automatic" | "name" | "none";

const SOURCE_LABEL: Record<string, string> = {
  chosen: "chosen",
  none: "none chosen",
  collects: "from Collects",
  name: "from the name",
  parent: "collected editions",
};

function describeSource(group: SeriesGroup | undefined): string {
  if (!group?.source) return "automatic";
  return SOURCE_LABEL[group.source] ?? "automatic";
}

function errorText(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.userMessage : fallback;
}

export function SeriesGroupPanel({ comicId }: { comicId: string }) {
  const group = useSeriesGroup(comicId);
  const update = useUpdateSeriesGroup();
  const retag = useRetagSeries();
  const { addToast } = useToast();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("automatic");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const data = group.data;

  const openDialog = () => {
    setError(null);
    setName(data?.value ?? "");
    setMode(
      !data?.chosen ? "automatic" : data.source === "none" ? "none" : "name",
    );
    setOpen(true);
  };

  const save = async () => {
    setError(null);
    const value = mode === "automatic" ? null : mode === "none" ? "" : name;
    try {
      const result = await update.mutateAsync({ comicId, value });
      setOpen(false);
      addToast({
        type: "success",
        title: "Series group saved",
        description: `${
          result.value ? `Group: ${result.value}.` : "No group."
        } Re-tag the files to write it into them.`,
      });
    } catch (saveError) {
      setError(errorText(saveError, "Comicarr could not save the group."));
    }
  };

  const runRetag = async () => {
    try {
      await retag.mutateAsync(comicId);
      addToast({
        type: "success",
        title: "Re-tagging started",
        description:
          "Comicarr is writing the tags into this series' files in the background.",
      });
    } catch (retagError) {
      addToast({
        type: "error",
        title: "Could not start re-tagging",
        description: errorText(retagError, "The log has the reason."),
      });
    }
  };

  if (group.isError) return null;

  return (
    <section
      className="mb-3.5 max-w-[640px] rounded-md border border-border p-3"
      aria-labelledby="series-group-title"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span id="series-group-title" className="text-xs font-semibold">
              Series group
            </span>
            <span className="mono-label">{describeSource(data)}</span>
          </div>
          <p className="mono-meta mt-1 break-all" data-testid="series-group">
            {group.isLoading ? "…" : (data?.value ?? "None")}
          </p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Written to ComicInfo as SeriesGroup. Readers such as Kavita collect
            series that share it.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void runRetag()}
            disabled={retag.isPending}
          >
            {retag.isPending ? (
              <LoaderCircle
                className="animate-spin motion-reduce:animate-none"
                aria-hidden="true"
              />
            ) : null}
            Re-tag files
          </Button>
          <Button variant="outline" size="sm" onClick={openDialog}>
            <Tags aria-hidden="true" />
            Change group
          </Button>
        </div>
      </div>

      <Dialog
        open={open}
        onOpenChange={(next) => !update.isPending && setOpen(next)}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Series group</DialogTitle>
            <DialogDescription>
              The group the files of this series are tagged with. New files get
              it when they are tagged; re-tag to update the files you have.
            </DialogDescription>
          </DialogHeader>
          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            <fieldset className="grid gap-2">
              <legend className="sr-only">Group</legend>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="series-group-mode"
                  checked={mode === "automatic"}
                  onChange={() => setMode("automatic")}
                  className="mt-1 accent-primary"
                />
                <span>
                  Work it out automatically
                  <span className="block text-xs text-muted-foreground">
                    From what a collected edition collects, or the name before
                    its colon. Single issues join when an edition points at
                    them.
                  </span>
                </span>
              </label>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="series-group-mode"
                  checked={mode === "name"}
                  onChange={() => setMode("name")}
                  className="mt-1 accent-primary"
                />
                <span>Use this name</span>
              </label>
              {mode === "name" ? (
                <div className="grid gap-1.5 pl-6">
                  <Label htmlFor="series-group-name" className="sr-only">
                    Group name
                  </Label>
                  <Input
                    id="series-group-name"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Die"
                    autoComplete="off"
                    maxLength={200}
                    autoFocus
                  />
                </div>
              ) : null}
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="series-group-mode"
                  checked={mode === "none"}
                  onChange={() => setMode("none")}
                  className="mt-1 accent-primary"
                />
                <span>
                  No group
                  <span className="block text-xs text-muted-foreground">
                    Re-tagging removes a group the files already carry.
                  </span>
                </span>
              </label>
            </fieldset>

            {error ? (
              <p role="alert" className="text-sm text-[var(--status-error)]">
                {error}
              </p>
            ) : null}

            <DialogFooter className="gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={update.isPending}
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={update.isPending || (mode === "name" && !name.trim())}
                aria-busy={update.isPending}
              >
                {update.isPending ? "Saving…" : "Save group"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </section>
  );
}

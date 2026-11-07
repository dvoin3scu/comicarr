/**
 * Fork: preview, then rename, a series' files to its naming format.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import {
  useRenameFiles,
  useRenamePreview,
  type RenameItem,
} from "@/hooks/useSeriesPlacement";
import { ApiError } from "@/lib/api";

interface RenameFilesDialogProps {
  comicId: string;
  issueIds?: string[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function errorText(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.userMessage : fallback;
}

function RenameRow({ item }: { item: RenameItem }) {
  return (
    <li className="grid gap-0.5 py-1.5" data-testid="rename-item">
      <span className="break-all font-mono text-xs text-muted-foreground">
        {item.current}
      </span>
      <span className="break-all font-mono text-xs">
        → {item.proposed}
        {item.status === "conflict" ? (
          <span className="ml-2 text-[var(--status-error)]">
            already exists, skipped
          </span>
        ) : null}
      </span>
    </li>
  );
}

export function RenameFilesDialog({
  comicId,
  issueIds,
  open,
  onOpenChange,
}: RenameFilesDialogProps) {
  const preview = useRenamePreview({ comicId, issueIds }, open);
  const rename = useRenameFiles();
  const { addToast } = useToast();
  const [error, setError] = useState<string | null>(null);

  const plan = preview.data;
  const changes = plan?.items.filter((item) => item.status !== "unchanged");
  const unchanged = (plan?.items.length ?? 0) - (changes?.length ?? 0);
  const format = plan?.content_type === "manga" ? "manga" : "comic";

  const close = (next: boolean) => {
    if (rename.isPending) return;
    setError(null);
    onOpenChange(next);
  };

  const apply = async () => {
    setError(null);
    try {
      const result = await rename.mutateAsync({ comicId, issueIds });
      if (!result.success) {
        setError(result.errors[0] ?? "Comicarr could not rename every file.");
        return;
      }
      onOpenChange(false);
      addToast({
        type: "success",
        title: "Files renamed",
        description: `${result.renamed} file${result.renamed === 1 ? "" : "s"} renamed.`,
      });
    } catch (renameError) {
      setError(errorText(renameError, "Comicarr could not rename the files."));
    }
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Rename files</DialogTitle>
          <DialogDescription>
            Gives each file the name the {format} file format asks for. Files
            stay in their folder.
          </DialogDescription>
        </DialogHeader>

        {preview.isLoading ? (
          <p className="text-sm text-muted-foreground">Checking the files…</p>
        ) : preview.isError ? (
          <p role="alert" className="text-sm text-[var(--status-error)]">
            {errorText(preview.error, "Comicarr could not check the files.")}
          </p>
        ) : plan ? (
          <div className="grid gap-2">
            <p className="text-sm" data-testid="rename-summary">
              {plan.to_rename === 0
                ? "Every file already has the right name."
                : `${plan.to_rename} file${plan.to_rename === 1 ? "" : "s"} to rename.`}
              {unchanged > 0 && plan.to_rename > 0
                ? ` ${unchanged} already named correctly.`
                : ""}
            </p>
            {changes && changes.length > 0 ? (
              <ul className="max-h-[50vh] divide-y divide-border overflow-y-auto">
                {changes.map((item) => (
                  <RenameRow
                    key={`${item.table}:${item.issue_id}`}
                    item={item}
                  />
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        {error ? (
          <p role="alert" className="text-sm text-[var(--status-error)]">
            {error}
          </p>
        ) : null}

        <DialogFooter className="gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={rename.isPending}
            onClick={() => close(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => void apply()}
            disabled={rename.isPending || !plan || plan.to_rename === 0}
            aria-busy={rename.isPending}
          >
            {rename.isPending
              ? "Renaming…"
              : plan && plan.to_rename > 0
                ? `Rename ${plan.to_rename} file${plan.to_rename === 1 ? "" : "s"}`
                : "Rename files"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

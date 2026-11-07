/**
 * Fork: the Files menu. Renames a series' files to its naming format (with a
 * preview first) or re-tags them. With issueIds it acts on those issues only,
 * which is how the issue selection bar uses it.
 */
import { useState } from "react";
import { ChevronDown, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useToast } from "@/components/ui/toast";
import { useRetagFiles } from "@/hooks/useSeriesPlacement";
import { ApiError } from "@/lib/api";
import { RenameFilesDialog } from "./RenameFilesDialog";

interface SeriesFilesMenuProps {
  comicId: string;
  /** Act on these issues only; omitted for the whole series. */
  issueIds?: string[];
  disabled?: boolean;
}

export function SeriesFilesMenu({
  comicId,
  issueIds,
  disabled = false,
}: SeriesFilesMenuProps) {
  const retag = useRetagFiles();
  const { addToast } = useToast();
  const [renaming, setRenaming] = useState(false);
  const scope = issueIds
    ? `${issueIds.length} selected issue${issueIds.length === 1 ? "" : "s"}`
    : "this series";

  const runRetag = async () => {
    try {
      await retag.mutateAsync({ comicId, issueIds });
      addToast({
        type: "success",
        title: "Re-tagging started",
        description: `Comicarr is writing the tags into the files of ${scope} in the background.`,
      });
    } catch (retagError) {
      addToast({
        type: "error",
        title: "Could not start re-tagging",
        description:
          retagError instanceof ApiError
            ? retagError.userMessage
            : "The log has the reason.",
      });
    }
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          disabled={disabled || retag.isPending}
          render={
            <Button
              type="button"
              variant="outline"
              size="toolbar"
              aria-label={
                issueIds ? "File actions for selected issues" : "File actions"
              }
            >
              <FileText />
              Files
              <ChevronDown aria-hidden="true" />
            </Button>
          }
        />
        <DropdownMenuContent align="start" sideOffset={4}>
          <DropdownMenuItem onClick={() => setRenaming(true)}>
            Rename files…
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => void runRetag()}>
            Re-tag files
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <RenameFilesDialog
        comicId={comicId}
        issueIds={issueIds}
        open={renaming}
        onOpenChange={setRenaming}
      />
    </>
  );
}

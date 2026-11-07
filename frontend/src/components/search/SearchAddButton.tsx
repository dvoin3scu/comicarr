import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Check, FolderPlus, Loader2 } from "lucide-react";
import { useAddComic, useAddManga } from "@/hooks/useSearch";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FolderChoice } from "@/components/series/FolderChoice";
import {
  useAddFolderChoice,
  type AddTarget,
} from "@/components/search/useAddFolderChoice";
import type { ComicAddedDetail, SearchResult, ContentType } from "@/types";

interface SearchAddButtonProps {
  comic: SearchResult;
  contentType: ContentType;
  /** Extra classes for layout, e.g. a full-width button on a grid card. */
  className?: string;
}

export default function SearchAddButton({
  comic,
  contentType,
  className = "",
}: SearchAddButtonProps) {
  const [isAdded, setIsAdded] = useState(comic.in_library ?? false);
  const [isProcessing, setIsProcessing] = useState(false);
  const addComicMutation = useAddComic();
  const addMangaMutation = useAddManga();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const comicIdRef = useRef<string | null>(null);
  const [folderOpen, setFolderOpen] = useState(false);
  const [folderError, setFolderError] = useState<string | null>(null);

  const isManga = contentType === "manga";
  const choice = useAddFolderChoice(isManga, folderOpen);
  const itemLabel = isManga ? "Manga" : "Comic";

  useEffect(() => {
    if (!isProcessing || !comicIdRef.current) return;
    let cancelled = false;

    const handleAddById = (event: CustomEvent<string>) => {
      if (cancelled) return;
      try {
        const data: ComicAddedDetail = JSON.parse(event.detail);
        if (data.comicid === comicIdRef.current) {
          if (data.status === "success") {
            navigate(`/library/${comicIdRef.current}`);
            setIsProcessing(false);
            comicIdRef.current = null;
          } else if (data.status === "failure") {
            addToast({
              type: "error",
              title: "Failed to Add Series",
              description:
                data.message || "An error occurred while adding the series.",
            });
            setIsProcessing(false);
            setIsAdded(false);
            comicIdRef.current = null;
          }
        }
      } catch (error) {
        console.error("Error parsing comic-added event:", error);
      }
    };

    window.addEventListener("comic-added", handleAddById as EventListener);
    return () => {
      cancelled = true;
      window.removeEventListener("comic-added", handleAddById as EventListener);
    };
  }, [isProcessing, navigate, addToast]);

  const add = async ({ folder, root }: AddTarget = {}) => {
    const id = comic.comicid ?? comic.id;
    comicIdRef.current = id ?? null;
    setIsProcessing(true);
    try {
      const input = folder ? { id, folder } : root ? { id, root } : id;
      const response = (
        isManga
          ? await addMangaMutation.mutateAsync(input)
          : await addComicMutation.mutateAsync(input)
      ) as {
        comicid?: string;
      };
      if (response?.comicid) {
        comicIdRef.current = response.comicid;
      }
      setIsAdded(true);
      addToast({
        type: "success",
        title: `Adding ${itemLabel}...`,
        description:
          folder || root
            ? `${comic.name} is being added to ${folder ?? root}. Please wait...`
            : `${comic.name} is being added to your library. Please wait...`,
        duration: 5000,
      });
    } catch (err) {
      setIsProcessing(false);
      setIsAdded(false);
      comicIdRef.current = null;
      throw err;
    }
  };

  const handleAdd = async (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    try {
      await add();
    } catch (err) {
      addToast({
        type: "error",
        title: `Failed to Add ${itemLabel}`,
        description: err instanceof Error ? err.message : "Unknown error",
      });
    }
  };

  const handleFolderAdd = async () => {
    setFolderError(null);
    try {
      await add(choice.target());
      setFolderOpen(false);
    } catch (err) {
      setFolderError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const base = `inline-flex items-center justify-center gap-1 px-2.5 py-1 rounded-control border font-mono text-[11px] transition-colors ${className}`;

  if (isAdded) {
    return (
      <button
        type="button"
        disabled
        aria-label={`${comic.name} added`}
        className={base}
        style={{
          borderColor: "var(--border)",
          color: "var(--status-active)",
        }}
      >
        <Check className="w-3 h-3" />
        added
      </button>
    );
  }

  if (isProcessing) {
    return (
      <button
        type="button"
        disabled
        aria-label={`Adding ${comic.name}`}
        className={base}
        style={{
          borderColor: "var(--border)",
          color: "var(--muted-foreground)",
        }}
      >
        <Loader2 className="w-3 h-3 animate-spin" />
        adding…
      </button>
    );
  }

  const isPending = isManga
    ? addMangaMutation.isPending
    : addComicMutation.isPending;

  return (
    <div className={`inline-flex gap-1 ${className}`}>
      <button
        type="button"
        onClick={handleAdd}
        disabled={isPending}
        aria-label={`Add ${comic.name}`}
        className={`${base} flex-1 hover:bg-[color-mix(in_oklab,var(--primary)_14%,transparent)]`}
        style={{
          borderColor: "var(--primary)",
          color: "var(--primary)",
        }}
      >
        <Plus className="w-3 h-3" />
        {isPending ? "adding…" : "add"}
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setFolderError(null);
          choice.reset();
          setFolderOpen(true);
        }}
        disabled={isPending}
        aria-label={`Add ${comic.name} to a chosen folder`}
        title="Add to a chosen folder"
        className="inline-flex items-center justify-center rounded-control border border-border px-1.5 text-muted-foreground transition-colors hover:text-foreground"
      >
        <FolderPlus className="w-3 h-3" aria-hidden="true" />
      </button>

      <Dialog open={folderOpen} onOpenChange={setFolderOpen}>
        <DialogContent
          className="max-w-md"
          onClick={(e) => e.stopPropagation()}
        >
          <DialogHeader>
            <DialogTitle>Add {comic.name} to a folder</DialogTitle>
            <DialogDescription>
              Choose the library root for this series, or type a folder inside
              one of your library roots.
            </DialogDescription>
          </DialogHeader>
          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              void handleFolderAdd();
            }}
          >
            <FolderChoice
              name={`add-folder-${comic.comicid ?? comic.id}`}
              options={choice.options}
              selected={choice.selected}
              onSelect={choice.setSelected}
              other={choice.other}
              onOtherChange={choice.setOther}
              loading={choice.loading}
            />
            {folderError ? (
              <p role="alert" className="text-sm text-[var(--status-error)]">
                {folderError}
              </p>
            ) : null}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setFolderOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isPending}>
                Add {itemLabel.toLowerCase()}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

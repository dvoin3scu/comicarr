import { ph, t } from "@lingui/core/macro";
import { Trans } from "@lingui/react/macro";
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
              title: t`Failed to Add Series`,
              description:
                data.message || t`An error occurred while adding the series.`,
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

  const add = async (target: AddTarget = {}) => {
    const { root } = target;
    // Fork: a chosen library root reads like a folder in the toast below.
    const folder = target.folder ?? root;
    const id = comic.comicid ?? comic.id;
    comicIdRef.current = id ?? null;
    setIsProcessing(true);
    try {
      const input = target.folder
        ? { id, folder: target.folder }
        : root
          ? { id, root }
          : id;
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
        title: isManga ? t`Adding manga...` : t`Adding comic...`,
        description: folder
          ? t`${ph({ name: comic.name })} is being added to ${folder}. Please wait...`
          : t`${ph({ name: comic.name })} is being added to your library. Please wait...`,
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
        title: isManga ? t`Failed to Add Manga` : t`Failed to Add Comic`,
        description: err instanceof Error ? err.message : t`Unknown error`,
      });
    }
  };

  const handleFolderAdd = async () => {
    setFolderError(null);
    try {
      await add(choice.target());
      setFolderOpen(false);
    } catch (err) {
      setFolderError(err instanceof Error ? err.message : t`Unknown error`);
    }
  };

  const baseClass = `inline-flex h-8 items-center justify-center gap-1.5 rounded-control border border-border-strong bg-surface-1 px-3 text-[13px] font-medium transition-colors ${className}`;

  if (isAdded) {
    return (
      <button
        type="button"
        disabled
        aria-label={t`${ph({ name: comic.name })} added`}
        className={`${baseClass} text-foreground-2`}
      >
        <Check className="size-3.5 text-[var(--status-active)]" />
        <Trans>Added</Trans>
      </button>
    );
  }

  if (isProcessing) {
    return (
      <button
        type="button"
        disabled
        aria-label={t`Adding ${ph({ name: comic.name })}`}
        className={`${baseClass} text-muted-foreground`}
      >
        <Loader2 className="size-3.5 animate-spin" />
        <Trans>Adding…</Trans>
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
        aria-label={t`Add ${ph({ name: comic.name })}`}
        className={`${baseClass} flex-1 text-foreground hover:border-border-emphasis hover:bg-surface-2`}
      >
        <Plus className="size-3.5" />
        {isPending ? t`Adding…` : t`Add`}
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
        aria-label={t`Add ${ph({ name: comic.name })} to a chosen folder`}
        title={t`Add to a chosen folder`}
        className="inline-flex h-8 w-8 items-center justify-center rounded-control border border-border-subtle text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
      >
        <FolderPlus className="size-3.5" aria-hidden="true" />
      </button>

      <Dialog open={folderOpen} onOpenChange={setFolderOpen}>
        <DialogContent
          className="max-w-md"
          onClick={(e) => e.stopPropagation()}
        >
          <DialogHeader>
            <DialogTitle>
              {t`Add ${ph({ name: comic.name })} to a folder`}
            </DialogTitle>
            <DialogDescription>
              <Trans>
                Choose a folder on the server, inside one of your library roots.
                Leave it empty to use the automatic folder.
              </Trans>
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
                <Trans>Cancel</Trans>
              </Button>
              <Button type="submit" disabled={isPending}>
                {isManga ? t`Add manga` : t`Add comic`}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

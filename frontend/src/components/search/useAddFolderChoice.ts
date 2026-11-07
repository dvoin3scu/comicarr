/**
 * Fork: state for the add dialog's choice of library root (the automatic
 * folder under that root), or a typed folder.
 */
import { useState } from "react";
import {
  OTHER_FOLDER,
  type FolderChoiceOption,
} from "@/components/series/FolderChoice";
import { useLibraryRoots } from "@/hooks/useSeriesPlacement";

export interface AddTarget {
  folder?: string;
  root?: string;
}

export function useAddFolderChoice(isManga: boolean, open: boolean) {
  const query = useLibraryRoots(open);
  const [picked, setPicked] = useState<string | null>(null);
  const [typed, setTyped] = useState("");

  const roots = query.data?.roots ?? [];
  const automaticRoot =
    (isManga ? query.data?.manga_default : query.data?.comic_default) ?? null;
  const ordered = automaticRoot
    ? [automaticRoot, ...roots.filter((root) => root !== automaticRoot)]
    : roots;

  const options: FolderChoiceOption[] = ordered.map((root) => ({
    value: root,
    label: `${root}/…`,
    hint:
      root === automaticRoot
        ? "Automatic folder"
        : "The automatic folder, under this root",
  }));

  const selected = picked ?? ordered[0] ?? OTHER_FOLDER;

  /** What to send: nothing for the automatic folder, else a root or a folder. */
  const target = (): AddTarget => {
    if (selected === OTHER_FOLDER) {
      const folder = typed.trim();
      return folder ? { folder } : {};
    }
    if (selected === automaticRoot) return {};
    return { root: selected };
  };

  return {
    options,
    selected,
    setSelected: setPicked,
    other: typed,
    setOther: setTyped,
    loading: open && query.isLoading,
    target,
    reset: () => {
      setPicked(null);
      setTyped("");
    },
  };
}

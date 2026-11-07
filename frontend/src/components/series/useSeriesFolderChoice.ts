/**
 * Fork: state for the series folder dialog's choice between the same folder
 * under each library root, or a typed one.
 */
import { useState } from "react";
import {
  OTHER_FOLDER,
  type FolderChoiceOption,
} from "@/components/series/FolderChoice";
import {
  useFolderOptions,
  type FolderOptions,
} from "@/hooks/useSeriesPlacement";

function samePath(left?: string | null, right?: string | null) {
  if (!left || !right) return false;
  const trim = (value: string) => value.replace(/\/+$/, "");
  return trim(left) === trim(right);
}

function initialChoice(
  data: FolderOptions | undefined,
  location: string | null | undefined,
) {
  const options = data?.options ?? [];
  const current = options.find((option) => samePath(option.folder, location));
  if (current) return { selected: current.folder, other: "" };
  if (!location) {
    const automatic = options.find((option) => option.automatic);
    if (automatic) return { selected: automatic.folder, other: "" };
  }
  return { selected: OTHER_FOLDER, other: location ?? "" };
}

export function useSeriesFolderChoice(
  comicId: string,
  location: string | null | undefined,
  open: boolean,
) {
  const query = useFolderOptions(comicId, open);
  const [picked, setPicked] = useState<string | null>(null);
  const [typed, setTyped] = useState<string | null>(null);

  const initial = initialChoice(query.data, location);
  const selected = picked ?? initial.selected;
  const other = typed ?? initial.other;
  const data = query.data?.options ?? [];

  const options: FolderChoiceOption[] = data.map((option) => ({
    value: option.folder,
    label: option.folder,
    hint: option.automatic ? "Automatic folder" : `Under ${option.root}`,
  }));

  const isAutomatic =
    selected !== OTHER_FOLDER &&
    data.some((option) => option.automatic && option.folder === selected);

  return {
    options,
    selected,
    setSelected: setPicked,
    other,
    setOther: setTyped,
    loading: open && query.isLoading,
    isAutomatic,
    folder: selected === OTHER_FOLDER ? other.trim() : selected,
    reset: () => {
      setPicked(null);
      setTyped(null);
    },
  };
}

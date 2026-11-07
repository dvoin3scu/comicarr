/**
 * Fork: library-root folder choices, the ComicInfo series group, and
 * renaming or re-tagging a series' files.
 * Kept in its own module so upstream hooks stay untouched.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";

export interface FolderOption {
  root: string;
  folder: string;
  automatic: boolean;
}

export interface FolderOptions {
  automatic: string | null;
  current: string | null;
  override: boolean;
  options: FolderOption[];
}

export interface LibraryRoots {
  roots: string[];
  comic_default: string | null;
  manga_default: string | null;
}

export type SeriesGroupSource =
  "chosen" | "none" | "collects" | "name" | "parent" | null;

export interface SeriesGroup {
  value: string | null;
  source: SeriesGroupSource;
  chosen: boolean;
}

export function useFolderOptions(
  comicId: string,
  enabled: boolean,
): UseQueryResult<FolderOptions> {
  return useQuery({
    queryKey: ["series", comicId, "folder-options"],
    queryFn: () =>
      apiRequest<FolderOptions>("GET", `/api/series/${comicId}/folder-options`),
    enabled,
  });
}

export function useLibraryRoots(
  enabled: boolean,
): UseQueryResult<LibraryRoots> {
  return useQuery({
    queryKey: ["library-roots"],
    queryFn: () => apiRequest<LibraryRoots>("GET", "/api/library-roots"),
    enabled,
    staleTime: 60_000,
  });
}

export function useSeriesGroup(comicId: string): UseQueryResult<SeriesGroup> {
  return useQuery({
    queryKey: ["series", comicId, "series-group"],
    queryFn: () =>
      apiRequest<SeriesGroup>("GET", `/api/series/${comicId}/series-group`),
  });
}

export interface SeriesGroupInput {
  comicId: string;
  /** A name, "" for no group, or null to work it out again. */
  value: string | null;
}

export function useUpdateSeriesGroup(): UseMutationResult<
  SeriesGroup,
  Error,
  SeriesGroupInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ comicId, value }) =>
      apiRequest<SeriesGroup>("PATCH", `/api/series/${comicId}/series-group`, {
        value,
      }),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["series"] });
    },
  });
}

export type RenameStatus = "rename" | "unchanged" | "conflict";

export interface RenameItem {
  issue_id: string;
  table: "issues" | "annuals";
  number: string | null;
  folder: string;
  current: string;
  proposed: string;
  status: RenameStatus;
}

export interface RenamePlan {
  content_type: "comic" | "manga";
  items: RenameItem[];
  to_rename: number;
  conflicts: number;
}

export interface RenameResult {
  success: boolean;
  renamed: number;
  conflicts: number;
  files: { issue_id: string; from: string; to: string }[];
  errors: string[];
}

export interface SeriesFilesInput {
  comicId: string;
  /** The issues to act on; omitted for the whole series. */
  issueIds?: string[];
}

function filesBody(issueIds?: string[]) {
  return issueIds ? { issue_ids: issueIds } : {};
}

export function useRenamePreview(
  { comicId, issueIds }: SeriesFilesInput,
  enabled: boolean,
): UseQueryResult<RenamePlan> {
  return useQuery({
    queryKey: ["rename-preview", comicId, issueIds ?? "all"],
    queryFn: () =>
      apiRequest<RenamePlan>(
        "POST",
        `/api/series/${comicId}/rename-preview`,
        filesBody(issueIds),
      ),
    enabled,
    gcTime: 0,
    staleTime: 0,
  });
}

export function useRenameFiles(): UseMutationResult<
  RenameResult,
  Error,
  SeriesFilesInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ comicId, issueIds }) =>
      apiRequest<RenameResult>(
        "POST",
        `/api/series/${comicId}/rename`,
        filesBody(issueIds),
      ),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["series"] });
    },
  });
}

/** Re-tag the whole series, or only the given issues. */
export function useRetagFiles(): UseMutationResult<
  unknown,
  Error,
  SeriesFilesInput
> {
  return useMutation({
    mutationFn: ({ comicId, issueIds }) =>
      issueIds
        ? apiRequest("POST", "/api/metadata/metatag/bulk", {
            comic_id: comicId,
            issue_ids: issueIds,
          })
        : apiRequest("POST", "/api/metadata/metatag/group", {
            comic_id: comicId,
          }),
  });
}

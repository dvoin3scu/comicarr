/**
 * Fork: library-root folder choices and the ComicInfo series group.
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

export function useRetagSeries(): UseMutationResult<unknown, Error, string> {
  return useMutation({
    mutationFn: (comicId: string) =>
      apiRequest("POST", "/api/metadata/metatag/group", { comic_id: comicId }),
  });
}

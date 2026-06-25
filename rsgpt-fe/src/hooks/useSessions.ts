// src/hooks/useSessions.ts
import { useInfiniteQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { GetChatSessionsListResponse } from "@/lib/types";

export const useInfiniteSessions = (pageSize = 10) =>
  useInfiniteQuery({
    queryKey: ["sessions", pageSize],
    initialPageParam: 1,
    queryFn: ({ pageParam = 1 }) =>
      apiFetch<GetChatSessionsListResponse>(
        `/chat/sessions?page=${pageParam}&page_size=${pageSize}`
      ),
    getNextPageParam: (lastPage) =>
      lastPage.has_next ? lastPage.page + 1 : undefined,
    staleTime: 1000 * 60 * 5,
  });
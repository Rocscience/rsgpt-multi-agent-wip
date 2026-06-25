import { useInfiniteQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { GetConversationHistoryResponse } from "@/lib/types";

export const useGetChatSessionHistory = (sessionId: string, pageSize = 10) =>
  useInfiniteQuery({
    queryKey: ["sessions/conversation", sessionId, pageSize],
    initialPageParam: 1,
    queryFn: ({ pageParam = 1 }) =>
      apiFetch<GetConversationHistoryResponse>(
        `/chat/sessions/conversation/${sessionId}?page=${pageParam}&page_size=${pageSize}`
      ),
    getNextPageParam: (lastPage) =>
      lastPage.has_next ? lastPage.page + 1 : undefined,
    staleTime: 1000 * 60 * 5,
  });
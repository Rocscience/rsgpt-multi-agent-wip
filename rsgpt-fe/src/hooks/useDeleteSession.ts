import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { DeleteResponse } from "@/lib/types";

export const useDeleteSession = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sessionId: string) =>
      apiFetch<DeleteResponse>(`/chat/sessions/${sessionId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      // Invalidate sessions list to refetch after deletion
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
};


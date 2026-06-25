// src/components/SideBar/SessionList.tsx
'use client'
import { useEffect, useMemo, useRef } from "react";
import { useParams } from "next/navigation";
import { useInfiniteSessions } from "@/hooks/useSessions";
import { SessionListItem } from "./session-list-item";
import { Skeleton, Alert, Button } from "@heroui/react";

interface SessionListProps {
  isMobile?: boolean;
  closeSidebar?: () => void;
}

export function SessionList({ isMobile = false, closeSidebar }: SessionListProps) {
  const params = useParams<{ sessionId?: string }>();
  const currentSessionId = params?.sessionId;
  
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
  } = useInfiniteSessions(25);

  const items = useMemo(
    () => data?.pages.flatMap((p) => p.sessions) ?? [],
    [data]
  );

  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!loadMoreRef.current) return;
    const el = loadMoreRef.current;

    const observer = new IntersectionObserver((entries) => {
      const [entry] = entries;
      if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    });

    observer.observe(el);
    return () => observer.unobserve(el);
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  // Initial loading state (no data yet)
  if (isLoading && items.length === 0) return (
    <div className="flex flex-col gap-1">
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="w-full">
          <div className="p-3 rounded-lg bg-default-100/50 animate-pulse">
            <Skeleton 
              className={`h-4 rounded-md bg-default-300 ${
                index % 3 === 0 ? 'w-4/5' : 
                index % 3 === 1 ? 'w-3/5' : 'w-2/3'
              }`} 
            />
          </div>
        </div>
      ))}
    </div>
  );

  // Show message when no sessions exist
  if (!isLoading && items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 px-4">
        <p className="text-sm text-secondary-foreground/50 text-center">
          No chats to show yet...
        </p>
      </div>
    );
  }

  const ErrorMessage = () => {
    if (!error) return null;

    // If we have some sessions, show a partial error message
    if (items.length > 0) {
      return (
        <div className="mt-2">
          <Alert
            color="warning"
            variant="flat"
            title="Failed to load more sessions"
            description={hasNextPage ? "There may be more sessions available." : ""}
          />
          <div className="mt-2 flex justify-center">
            <Button
              size="sm"
              color="warning"
              variant="flat"
              onClick={() => hasNextPage ? fetchNextPage() : refetch()}
              isLoading={isFetchingNextPage}
            >
              {hasNextPage ? "Retry Loading More" : "Refresh"}
            </Button>
          </div>
        </div>
      );
    }

    // No sessions loaded, show full error
    return (
      <div>
        <Alert
          color="danger"
          variant="flat"
          title="Failed to load sessions"
          description="Unable to retrieve your chat sessions."
        />
        <div className="mt-2 flex justify-center">
          <Button
            size="sm"
            color="danger"
            variant="flat"
            onClick={() => refetch()}
            isLoading={isLoading}
          >
            Retry
          </Button>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-1">
      {items.map((session) => (
        <SessionListItem 
          key={session.chat_session_id} 
          session={session} 
          isActive={session.chat_session_id === currentSessionId}
          isMobile={isMobile}
          closeSidebar={closeSidebar}
          currentSessionId={currentSessionId}
        />
      ))}
      <ErrorMessage />
      <div ref={loadMoreRef} />
      {isFetchingNextPage && <Skeleton className="h-3 w-3/5 rounded-lg bg-default-200" />}
    </div>
  );
}
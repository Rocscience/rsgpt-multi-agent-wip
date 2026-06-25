'use client'

import { getProxiedAvatarUrl } from "@/lib/avatar";
import { Button, Avatar, Spinner, Tooltip, Skeleton } from "@heroui/react";
import { useUser } from "@auth0/nextjs-auth0";
import { useGetQuotaInfo } from "@/hooks/useGetQuotaInfo";
import { useAgentMode } from "@/hooks/useAgentMode";
import { useEffect, useState } from "react";
import { useSettingsModal } from "@/contexts/SettingsModalContext";

interface SidebarUserProfileProps {
  isCollapsed?: boolean;
}

export function SidebarUserProfile({ isCollapsed = false }: SidebarUserProfileProps) {
  const { user, isLoading } = useUser();
  const { data: quotaInfo, isPending } = useGetQuotaInfo(!!user);
  const { isAgentMode } = useAgentMode();
  const { isOpen: settingsModalOpen, openSettingsModal, closeSettingsModal } = useSettingsModal();
  const [avatarLoading, setAvatarLoading] = useState(true);
  
  // Calculate quota display based on mode
  const quotaUsed = isAgentMode ? quotaInfo?.agent_quota_used : quotaInfo?.questions_used;
  const quotaLimit = isAgentMode ? quotaInfo?.agent_quota : quotaInfo?.question_quota;
  const quotaLabel = isAgentMode ? 'agent requests' : 'questions';
  
  // Handle URL hash when modal opens/closes
  useEffect(() => {
    if (settingsModalOpen) {
      // Add #settings to URL when modal opens
      if (typeof window !== 'undefined') {
        window.history.pushState(null, '', '#settings');
      }
    } else {
      // Remove #settings from URL when modal closes
      if (typeof window !== 'undefined' && window.location.hash === '#settings') {
        window.history.pushState(null, '', window.location.pathname + window.location.search);
      }
    }
  }, [settingsModalOpen]);

  // Reset avatar loading state when user picture changes
  useEffect(() => {
    if (user?.picture) {
      setAvatarLoading(true);
    }
  }, [user?.picture]);

  if (isLoading || !user) return null;

  const displayName = user.name || user.nickname || (user.email ? user.email.split('@')[0] : 'User');
  const hasPlusAccess = (user as unknown as { rocPortalAccess?: boolean })?.rocPortalAccess;

  if (isCollapsed) {
    return (
      <div className="flex justify-center pb-2">
        <Tooltip content="Open account settings" placement="right">
          <Button
            isIconOnly
            variant="light"
            size="sm"
            aria-label="Open account settings"
            onPress={() => openSettingsModal('account-settings')}
          >
            {avatarLoading && user?.picture ? (
              <div className="relative">
                <Skeleton className="h-8 w-8 rounded-full" />
                <Avatar 
                  src={getProxiedAvatarUrl(user.picture)}
                  name={displayName}
                  size="sm"
                  className="absolute inset-0 opacity-0 shrink-0"
                  imgProps={{
                    onLoad: () => setAvatarLoading(false),
                    onError: () => setAvatarLoading(false)
                  }}
                />
              </div>
            ) : (
              <Avatar 
                src={getProxiedAvatarUrl(user?.picture)}
                name={displayName}
                size="sm"
                className="shrink-0"
                imgProps={{
                  onLoad: () => setAvatarLoading(false),
                  onError: () => setAvatarLoading(false)
                }}
              />
            )}
          </Button>
        </Tooltip>
      </div>
    );
  }

  return (
    <div className="pt-2 pb-1 h-full">
      <Tooltip content="Open account settings" placement="right">
        <Button
          className="flex items-center justify-start gap-2 px-1 py-3"
          fullWidth={true}
          variant="light"
          onPress={() => openSettingsModal('account-settings')}
        >
          {avatarLoading && user?.picture ? (
            <div className="relative">
              <Skeleton className="h-8 w-8 rounded-full" />
              <Avatar
                src={getProxiedAvatarUrl(user.picture)}
                name={displayName}
                size="sm"
                className="absolute inset-0 opacity-0 shrink-0"
                imgProps={{
                  onLoad: () => setAvatarLoading(false),
                  onError: () => setAvatarLoading(false)
                }}
              />
            </div>
          ) : (
            <Avatar
              src={getProxiedAvatarUrl(user?.picture)}
              name={displayName}
              size="sm"
              className="shrink-0"
              imgProps={{
                onLoad: () => setAvatarLoading(false),
                onError: () => setAvatarLoading(false)
              }}
            />
          )}
          <div className="flex flex-col items-start gap-0.5">
            <span className="text-foreground text-sm leading-tight">{displayName}</span>
            {hasPlusAccess && isPending ? (
              <Spinner size="sm" color="primary" />
            ) : (
              <span className={`text-xs leading-tight ${isAgentMode ? 'text-blue-500/70' : 'text-secondary-foreground/70'}`}>
                {quotaUsed} / {quotaLimit} {quotaLabel} used
              </span>
            )}
          </div>
        </Button>
      </Tooltip>
    </div>
  );
}


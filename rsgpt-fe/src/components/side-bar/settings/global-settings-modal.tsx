'use client';

import { useSettingsModal } from "@/contexts/SettingsModalContext";
import { SettingsModal } from "./settings-modal";
import { useGetQuotaInfo } from "@/hooks/useGetQuotaInfo";
import { useUser } from "@auth0/nextjs-auth0";

export function GlobalSettingsModal() {
  const { user } = useUser();
  const { isOpen, initialTab, closeSettingsModal } = useSettingsModal();
  const { data: quotaInfo } = useGetQuotaInfo(!!user);

  // Don't render the modal at all if user is not logged in
  if (!user) {
    return null;
  }

  return (
    <SettingsModal
      organizationName={quotaInfo?.organization_name || 'Not available'}
      isOpen={isOpen}
      onClose={closeSettingsModal}
      initialTab={initialTab}
    />
  );
}

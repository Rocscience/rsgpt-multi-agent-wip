'use client';

import { Button, useDisclosure } from '@heroui/react';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { QuotaRequestModal } from '@/components/side-bar/settings/quota-request-modal';

interface AgentQuotaExceededBannerProps {
  currentQuota: number;
  currentUsed: number;
}

export function AgentQuotaExceededBanner({ 
  currentQuota, 
  currentUsed 
}: AgentQuotaExceededBannerProps) {
  const { isOpen, onOpen, onClose } = useDisclosure();

  return (
    <>
      <div className="w-full max-w-[768px] mx-auto px-2 sm:px-4 mb-2">
        <div className="flex items-center justify-between gap-3 px-4 py-3 bg-warning-50 dark:bg-warning-50/10 border border-warning-200 dark:border-warning-500/30 rounded-2xl">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0 w-9 h-9 rounded-full bg-warning-100 dark:bg-warning-500/20 flex items-center justify-center">
              <ExclamationTriangleIcon className="w-5 h-5 text-warning-600 dark:text-warning-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-warning-800 dark:text-warning-200">
                Agent quota reached
              </p>
              <p className="text-xs text-warning-600 dark:text-warning-400">
                You&apos;ve used {currentUsed} of {currentQuota} agent requests this month
              </p>
            </div>
          </div>
          <Button
            color="warning"
            variant="flat"
            size="sm"
            onPress={onOpen}
            className="flex-shrink-0 font-medium"
          >
            Request More
          </Button>
        </div>
      </div>
      
      <QuotaRequestModal
        isOpen={isOpen}
        onClose={onClose}
        currentQuota={currentQuota}
        currentUsed={currentUsed}
      />
    </>
  );
}

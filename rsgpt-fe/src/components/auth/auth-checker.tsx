'use client';

import { PortalAccountAlert } from '@/components/alerts/alerts';
import { useUpdateRocPortalStatus } from '@/hooks/useUpdateRocPortalStatus';
import { User } from '@auth0/nextjs-auth0/types';

interface AuthCheckerProps {
  user: User | null | undefined;
  isLoading: boolean;
  rocPortalAccess: boolean | null;
  setRocPortalAccess: (rocPortalAccess: boolean | null) => void;
}

export default function AuthChecker({ user, isLoading, rocPortalAccess, setRocPortalAccess }: AuthCheckerProps) {
  const { mutate: updateRocPortalStatus, isPending } = useUpdateRocPortalStatus();

  // Only show for authenticated users
  if (!user || isLoading) {
    return null;
  }

  // Show portal account alert when rocPortalAccess is false
  // This covers all account issues: not in ROC Portal, no organization assigned, etc.
  if (rocPortalAccess === false) {
    const handleRetry = () => {
      // Force refresh the rocportal status from the ROC Portal API
      updateRocPortalStatus(undefined, {
        onSuccess: (data) => {
          // Update local state to immediately hide the banner
          setRocPortalAccess(data.rocportal_status);
        },
        onError: (error) => {
          console.error('Error retrying RocPortal status:', error);
        }
      });
    };

    return (
      <div className="fixed top-[100px] right-4 z-50 max-w-lg">
        <PortalAccountAlert onRetry={handleRetry} isLoading={isPending} />
      </div>
    );
  }

  return null;
}

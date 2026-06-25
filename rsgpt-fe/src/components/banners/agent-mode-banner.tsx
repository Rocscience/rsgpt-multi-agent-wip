'use client';

import { useState, useEffect } from "react";
import { Alert, Button, Skeleton } from "@heroui/react";
import { SparklesIcon, ArrowDownTrayIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useGetUserSettings } from "@/hooks/useGetUserSettings";
import { useGetDeviceInfo } from "@/hooks/useGetDeviceInfo";
import { useUser } from "@auth0/nextjs-auth0";
import { useSettingsModal } from "@/contexts/SettingsModalContext";
import { apiFetch } from "@/lib/api";

const BANNER_DISMISSED_KEY = 'agent-mode-banner-dismissed';

interface AgentModeBannerProps {
  variant?: 'chat' | 'dashboard';
}

interface DesktopPresignedUrlResponse {
  download_url: string;
  filename: string;
  size_bytes?: number;
  checksum_sha256?: string;
}

export function AgentModeBanner({ variant = 'chat' }: AgentModeBannerProps) {
  const { user, isLoading: isUserLoading } = useUser();
  const { data: userSettings, isLoading: isSettingsLoading } = useGetUserSettings(!!user);
  const { openSettingsModal } = useSettingsModal();
  const [isDownloading, setIsDownloading] = useState(false);
  const [isDismissed, setIsDismissed] = useState<boolean | null>(null);

  const isLoggedIn = !isUserLoading && !!user;
  const isOptedIn = userSettings?.agent_mode_opt_in ?? false;
  const rocPortalAccess = (user as unknown as { rocPortalAccess?: boolean })?.rocPortalAccess;
  
  // Check if account setup is incomplete (rocPortal access denied = not in ROC Portal or no organization)
  const hasAccountError = rocPortalAccess === false;

  // Only fetch device info for opted-in users (to check if they have an active device)
  const { data: deviceInfo, isLoading: isDeviceInfoLoading } = useGetDeviceInfo(isOptedIn);
  const hasActiveDevice = isOptedIn && deviceInfo?.devices?.some(device => device.is_active);

  // Check localStorage on mount for dismissed state
  useEffect(() => {
    const dismissed = localStorage.getItem(BANNER_DISMISSED_KEY) === 'true';
    setIsDismissed(dismissed);
  }, []);

  // Check if still loading (used for skeleton display on chat page for non-logged-in users)
  const isLoading = isUserLoading;

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const response = await apiFetch<DesktopPresignedUrlResponse>('/desktop/presigned-url');
      window.open(response.download_url, '_blank');
    } catch (error) {
      console.error('Failed to download desktop app:', error);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleDismiss = () => {
    localStorage.setItem(BANNER_DISMISSED_KEY, 'true');
    setIsDismissed(true);
  };

  const handleOpenConsent = () => {
    openSettingsModal('data-consent');
  };

  const handleLogin = () => {
    window.location.href = '/auth/login';
  };

  // Skeleton content for loading state
  const skeletonContent = (
    <div className="flex items-center gap-3 flex-wrap justify-center">
      <span className="flex items-center gap-2">
        <Skeleton className="w-5 h-5 rounded-full bg-primary/30" />
        <Skeleton className="h-4 w-36 sm:w-72 rounded-md bg-primary/30" />
      </span>
      <Skeleton className="h-8 w-24 rounded-lg bg-primary/30" />
    </div>
  );

  // Determine message and button based on auth/opt-in state
  const getMessage = () => {
    if (!isLoggedIn) {
      return {
        mobile: "Unlock Agent Mode",
        desktop: "Unlock Agent Mode — our most powerful feature yet."
      };
    }
    // Show account setup required message if there's an error
    if (hasAccountError) {
      return {
        mobile: "Account setup required",
        desktop: "Complete your account setup to unlock Agent Mode."
      };
    }
    if (isOptedIn) {
      return {
        mobile: "Get started with Agent Mode",
        desktop: "You've unlocked Agent Mode! Download the app to get started."
      };
    }
    return {
      mobile: "Unlock Agent Mode",
      desktop: "Unlock Agent Mode — our most powerful feature yet."
    };
  };

  const renderButton = () => {
    if (!isLoggedIn) {
      return (
        <Button
          size="sm"
          variant="solid"
          color="primary"
          onPress={handleLogin}
        >
          Opt In
        </Button>
      );
    }
    // Don't show opt-in button if account is not properly set up
    if (hasAccountError) {
      return null;
    }
    if (isOptedIn) {
      return (
        <Button
          size="sm"
          variant="solid"
          color="primary"
          startContent={!isDownloading && <ArrowDownTrayIcon className="w-4 h-4" />}
          onPress={handleDownload}
          isLoading={isDownloading}
        >
          Download
        </Button>
      );
    }
    return (
      <Button
        size="sm"
        variant="solid"
        color="primary"
        onPress={handleOpenConsent}
      >
        Opt In
      </Button>
    );
  };

  const message = getMessage();

  // Don't render anything until we've checked localStorage for dismissed state
  if (isDismissed === null) {
    return null;
  }

  // On dashboard, always wait for auth to complete before rendering anything
  if (variant === 'dashboard' && isUserLoading) {
    return null;
  }

  // For logged-in users, wait for settings to load before deciding
  // This prevents skeleton flash while we check opt-in status
  if (isLoggedIn && isSettingsLoading) {
    return null;
  }

  // For opted-in users, wait for device info to load before deciding
  // This prevents skeleton flash while we check for active devices
  if (isOptedIn && isDeviceInfoLoading) {
    return null;
  }

  // Don't show banner if user has opted in and dismissed it
  if (isOptedIn && isDismissed) {
    return null;
  }

  // Don't show banner if user has an active device (already set up desktop app)
  if (hasActiveDevice) {
    return null;
  }

  // Loaded content
  const loadedContent = (
    <div className="flex items-center gap-3 flex-wrap justify-center">
      <span className="flex items-center gap-2 text-center">
        <SparklesIcon className="w-5 h-5 flex-shrink-0" />
        <span className="sm:hidden">{message.mobile}</span>
        <span className="hidden sm:inline">{message.desktop}</span>
      </span>
      {renderButton()}
      {isOptedIn && (
        <Button
          isIconOnly
          size="sm"
          variant="light"
          color="primary"
          aria-label="Dismiss banner"
          onPress={handleDismiss}
          className="ml-1"
        >
          <XMarkIcon className="w-4 h-4" />
        </Button>
      )}
    </div>
  );

  return (
    <Alert
      color="primary"
      variant="flat"
      hideIcon
      hideIconWrapper
      classNames={{
        base: variant === 'chat' 
          ? "rounded-none absolute top-0 left-0 right-0 z-30" 
          : "rounded-none absolute top-[88px] left-0 right-0 z-30",
        mainWrapper: "flex-row items-center gap-2 justify-center",
      }}
    >
      {isLoading ? skeletonContent : loadedContent}
    </Alert>
  );
}

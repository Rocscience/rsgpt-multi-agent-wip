'use client';

import { Button, Checkbox, Divider } from "@heroui/react";
import { ArrowDownTrayIcon } from "@heroicons/react/24/outline";
import { useState, useEffect } from "react";
import { useGetUserSettings } from "@/hooks/useGetUserSettings";
import { useUpdateUserSettings } from "@/hooks/useUpdateUserSettings";
import { useGetQuotaInfo } from "@/hooks/useGetQuotaInfo";
import { useUser } from "@auth0/nextjs-auth0";
import { apiFetch } from "@/lib/api";

interface DesktopPresignedUrlResponse {
  download_url: string;
  filename: string;
  size_bytes?: number;
  checksum_sha256?: string;
}

interface DataConsentProps {
  onConsentChange?: (optedIn: boolean) => void;
}

export function DataConsent({ onConsentChange }: DataConsentProps) {
  const { user } = useUser();
  const { data: userSettings, isLoading } = useGetUserSettings(!!user);
  const { mutate: updateSettings, isPending } = useUpdateUserSettings();
  const { error: quotaError, isLoading: isQuotaLoading } = useGetQuotaInfo(!!user);
  
  // Check if account setup is incomplete (quota fetch failed = no organization)
  const hasAccountError = !!quotaError;
  
  const [isOptedIn, setIsOptedIn] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [isDownloading, setIsDownloading] = useState(false);

  // Sync local state with fetched settings
  useEffect(() => {
    if (userSettings) {
      setIsOptedIn(userSettings.agent_mode_opt_in ?? false);
    }
  }, [userSettings]);

  const handleCheckboxChange = (checked: boolean) => {
    setIsOptedIn(checked);
    setHasChanges(checked !== (userSettings?.agent_mode_opt_in ?? false));
  };

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

  const handleSave = () => {
    if (!userSettings) return;
    
    setSaveStatus('saving');
    updateSettings(
      {
        theme: userSettings.theme,
        preferred_sources: userSettings.preferred_sources,
        language: userSettings.language,
        timezone: userSettings.timezone,
        agent_mode_opt_in: isOptedIn,
      },
      {
        onSuccess: () => {
          setSaveStatus('success');
          setHasChanges(false);
          onConsentChange?.(isOptedIn);
          setTimeout(() => setSaveStatus('idle'), 2000);
        },
        onError: () => {
          setSaveStatus('error');
          setTimeout(() => setSaveStatus('idle'), 3000);
        },
      }
    );
  };

  const getSaveButtonText = () => {
    switch (saveStatus) {
      case 'saving': return 'Saving...';
      case 'success': return 'Saved!';
      case 'error': return 'Failed to save';
      default: return 'Save Changes';
    }
  };

  const getSaveButtonColor = () => {
    switch (saveStatus) {
      case 'success': return 'success';
      case 'error': return 'danger';
      default: return 'primary';
    }
  };

  if (isLoading || isQuotaLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <span className="text-foreground/60">Loading...</span>
      </div>
    );
  }

  // Show error state if account is not properly set up
  if (hasAccountError) {
    return (
      <div className="flex flex-col gap-4">
        <div className="rounded-lg p-4 border border-danger/50 bg-danger/10">
          <p className="text-sm text-danger font-medium mb-2">Account Setup Required</p>
          <p className="text-sm text-foreground/80">
            Your account is not linked to an organization. Agent Mode requires a complete account setup. 
            Please contact support or check your RocPortal account to resolve this issue.
          </p>
        </div>
        <Button 
          as="a" 
          href="https://www.rocscience.com/portal" 
          target="_blank"
          color="primary"
          variant="bordered"
          className="w-fit"
        >
          Go to RocPortal
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Agreement Statement */}
      <div className="rounded-lg p-4 border border-divider bg-background">
        <p className="text-sm text-foreground/80">
          If opted in to Agent Mode, data is collected to improve your experience with RSInsight, as well as to ensure the core functionality and security of RSInsight services.
        </p>
      </div>

      <Divider />

      {/* Consent Checkbox */}
      <div className="flex flex-col gap-3">
        <Checkbox
          isSelected={isOptedIn}
          onValueChange={handleCheckboxChange}
          classNames={{
            label: "text-sm text-foreground",
          }}
        >
          I agree to the data collection terms and want to enable Agent Mode features
        </Checkbox>

        {/* Current Status */}
        <div className="flex items-center gap-2 text-sm">
          <span className="text-foreground/60">Current status:</span>
          <span className={`font-medium ${userSettings?.agent_mode_opt_in  ? 'text-success' : 'text-warning'}`}>
            {userSettings?.agent_mode_opt_in ? 'Opted In' : 'Opted Out'}
          </span>
        </div>

        {/* Save Button */}
        {hasChanges && (
          <Button
            color={getSaveButtonColor()}
            onPress={handleSave}
            isLoading={isPending || saveStatus === 'saving'}
            disabled={isPending || saveStatus === 'saving'}
            className="w-fit"
          >
            {getSaveButtonText()}
          </Button>
        )}
      </div>

      {/* Download Desktop App Section - Only shown for opted-in users */}
      {userSettings?.agent_mode_opt_in && (
        <>
          <Divider />
          <div className="flex flex-col gap-3">
            <p className="text-sm font-medium text-foreground">Desktop App</p>
            <p className="text-sm text-foreground/80">
              Download the RSInsight desktop app to use Agent Mode features.
            </p>
            <Button
              color="primary"
              variant="bordered"
              startContent={!isDownloading && <ArrowDownTrayIcon className="w-4 h-4" />}
              onPress={handleDownload}
              isLoading={isDownloading}
              className="w-fit"
            >
              Download App
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { Button, Progress } from '@heroui/react';

type UpdateState = 'idle' | 'checking' | 'available' | 'downloading' | 'downloaded' | 'error';

interface UpdateInfo {
  version: string;
  releaseDate?: string;
}

interface DownloadProgress {
  percent: number;
  transferred: number;
  total: number;
  bytesPerSecond: number;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

const SNOOZE_KEY = 'autoUpdateSnoozeUntil';
const SNOOZE_DURATION = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

export const AutoUpdateBanner: React.FC = () => {
  const [state, setState] = useState<UpdateState>('idle');
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [progress, setProgress] = useState<DownloadProgress | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [dismissed, setDismissed] = useState(false);
  const [snoozed, setSnoozed] = useState(false);

  useEffect(() => {
    if (!window.electron?.autoUpdate) return;

    // Check if update is snoozed
    const checkSnooze = () => {
      const snoozeUntil = localStorage.getItem(SNOOZE_KEY);
      if (snoozeUntil) {
        const snoozeTime = parseInt(snoozeUntil, 10);
        const now = Date.now();
        if (now < snoozeTime) {
          setSnoozed(true);
          return true;
        } else {
          // Snooze expired, clear it
          localStorage.removeItem(SNOOZE_KEY);
          setSnoozed(false);
          return false;
        }
      }
      return false;
    };

    // Check snooze status on mount
    checkSnooze();

    const cleanups: (() => void)[] = [];

    cleanups.push(window.electron.autoUpdate.onChecking(() => {
      setState('checking');
    }));

    cleanups.push(window.electron.autoUpdate.onUpdateAvailable((info) => {
      setState('available');
      setUpdateInfo(info);
      setDismissed(false);
      // Check snooze - if snoozed, don't show
      checkSnooze();
    }));

    cleanups.push(window.electron.autoUpdate.onUpdateNotAvailable(() => {
      setState('idle');
    }));

    cleanups.push(window.electron.autoUpdate.onDownloadProgress((prog) => {
      setState('downloading');
      setProgress(prog);
    }));

    cleanups.push(window.electron.autoUpdate.onUpdateDownloaded((info) => {
      setState('downloaded');
      setUpdateInfo(info);
      setDismissed(false);

      // Auto-restart after 3 seconds to give user a moment to see the message
      setTimeout(() => {
        window.electron.autoUpdate.installUpdate();
      }, 3000);
    }));

    cleanups.push(window.electron.autoUpdate.onError((error) => {
      setState('error');
      setErrorMessage(error.message);
    }));

    return () => cleanups.forEach(fn => fn());
  }, []);

  const handleDownload = async () => {
    await window.electron.autoUpdate.downloadUpdate();
  };

  const handleInstall = async () => {
    await window.electron.autoUpdate.installUpdate();
  };

  const handleUpdateNow = async () => {
    // Download and auto-restart when complete
    await window.electron.autoUpdate.downloadUpdate();
    // Note: When download completes, the 'downloaded' state will trigger
    // and we'll auto-restart via handleInstall
  };

  const handleLater = () => {
    // Snooze for 24 hours
    const snoozeUntil = Date.now() + SNOOZE_DURATION;
    localStorage.setItem(SNOOZE_KEY, snoozeUntil.toString());
    setSnoozed(true);
    setDismissed(true);
  };

  // Don't show if dismissed in current session, snoozed, idle, or checking
  if (dismissed || snoozed || state === 'idle' || state === 'checking') {
    return null;
  }

  return (
    <div className="bg-primary-50 border-b border-primary-200 px-4 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        {state === 'available' && updateInfo && (
          <>
            <span className="text-sm text-primary-800">
              Version {updateInfo.version} is available.
            </span>
            <div className="flex gap-2">
              <Button size="sm" variant="flat" onPress={handleLater}>
                Later
              </Button>
              <Button size="sm" color="primary" onPress={handleUpdateNow}>
                Update Now
              </Button>
            </div>
          </>
        )}

        {state === 'downloading' && progress && (
          <>
            <div className="flex-1">
              <span className="text-sm text-primary-800">
                Downloading update... {formatBytes(progress.transferred)} / {formatBytes(progress.total)}
              </span>
              <Progress
                size="sm"
                value={progress.percent}
                className="mt-1"
                color="primary"
              />
            </div>
          </>
        )}

        {state === 'downloaded' && updateInfo && (
          <>
            <span className="text-sm text-primary-800">
              Update downloaded! Restarting in 3 seconds...
            </span>
            <Button size="sm" color="primary" onPress={handleInstall}>
              Restart Now
            </Button>
          </>
        )}

        {state === 'error' && (
          <>
            <span className="text-sm text-danger-600">
              Update failed: {errorMessage}
            </span>
            <Button size="sm" variant="flat" onPress={() => setDismissed(true)}>
              Dismiss
            </Button>
          </>
        )}
      </div>
    </div>
  );
};

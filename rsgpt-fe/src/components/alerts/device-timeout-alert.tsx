'use client';

import { useEffect, useState } from 'react';
import { Alert } from '@heroui/react';

export function DeviceTimeoutAlert() {
  const [showAlert, setShowAlert] = useState(false);

  useEffect(() => {
    const handleDeviceTimeout = () => {
      setShowAlert(true);
      // Auto-dismiss after 7 seconds
      setTimeout(() => setShowAlert(false), 7000);
    };

    window.addEventListener('device-timeout', handleDeviceTimeout);

    return () => {
      window.removeEventListener('device-timeout', handleDeviceTimeout);
    };
  }, []);

  if (!showAlert) return null;

  return (
    <div className="fixed top-4 right-4 z-50 max-w-md">
      <Alert
        color="warning"
        variant="flat"
        title="Request Timed Out"
        description="The request timed out before we got a response. Please try again."
        isClosable
        onClose={() => setShowAlert(false)}
      />
    </div>
  );
}


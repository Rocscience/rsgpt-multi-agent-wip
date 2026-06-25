'use client';

import { useEffect, useState } from 'react';
import { Alert } from '@heroui/react';

export function DeviceConnectionAlert() {
  const [showAlert, setShowAlert] = useState(false);

  useEffect(() => {
    const handleDeviceDisconnected = () => {
      setShowAlert(true);
      // Auto-dismiss after 7 seconds
      setTimeout(() => setShowAlert(false), 7000);
    };

    window.addEventListener('device-disconnected', handleDeviceDisconnected);

    return () => {
      window.removeEventListener('device-disconnected', handleDeviceDisconnected);
    };
  }, []);

  if (!showAlert) return null;

  return (
    <div className="fixed top-4 right-4 z-50 max-w-md">
      <Alert
        color="warning"
        variant="flat"
        title="Device Not Connected"
        description="Your selected device is not connected. Please check your device connection and try again."
        isClosable
        onClose={() => setShowAlert(false)}
      />
    </div>
  );
}


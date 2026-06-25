'use client';

import { useEffect, useState } from 'react';
import { Alert } from '@heroui/react';
import { checkServiceHealth } from '@/lib/api';

export function ServiceStatusAlert() {
  const [isServiceDown, setIsServiceDown] = useState(false);
  const [showAlert, setShowAlert] = useState(false);

  useEffect(() => {
    // Initial health check
    checkServiceHealth();

    // Set up periodic health checks
    const healthCheckInterval = setInterval(() => {
      checkServiceHealth();
    }, 30000); // Check every 30 seconds

    // Listen for service events
    const handleServiceUnavailable = () => {
      setIsServiceDown(true);
      setShowAlert(true);
    };

    const handleServiceRecovered = () => {
      setIsServiceDown(false);
      // Keep alert visible for a moment to show recovery
      setTimeout(() => setShowAlert(false), 3000);
    };

    window.addEventListener('service-unavailable', handleServiceUnavailable);
    window.addEventListener('service-recovered', handleServiceRecovered);

    return () => {
      clearInterval(healthCheckInterval);
      window.removeEventListener('service-unavailable', handleServiceUnavailable);
      window.removeEventListener('service-recovered', handleServiceRecovered);
    };
  }, []);

  if (!showAlert) return null;

  return (
    <div className="fixed top-4 right-4 z-50 max-w-md">
      <Alert
        color={isServiceDown ? "danger" : "success"}
        variant="flat"
        title={isServiceDown ? "Service Unavailable" : "Service Recovered"}
        description={
          isServiceDown 
            ? "Some features may not work. We're working to restore service." 
            : "All features are now available."
        }
        isClosable={!isServiceDown}
        onClose={() => setShowAlert(false)}
      />
    </div>
  );
}

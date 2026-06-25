'use client';

import { Alert, Button } from "@heroui/react";
import { useGlobalAlerts, AlertType } from "@/hooks/useGlobalAlerts";
import { AnimatePresence, motion } from "framer-motion";

// Map alert types to HeroUI colors
const alertTypeToColor: Record<AlertType, "danger" | "warning" | "success" | "primary"> = {
  error: "danger",
  warning: "warning", 
  success: "success",
  info: "primary",
};

export function GlobalAlertContainer() {
  const { alerts, removeAlert } = useGlobalAlerts();

  if (alerts.length === 0) return null;

  return (
    <div className="fixed top-16 sm:top-20 md:top-24 right-2 sm:right-4 z-[60] flex flex-col gap-2 max-w-sm sm:max-w-md">
      <AnimatePresence mode="popLayout">
        {alerts.map((alert) => (
          <motion.div
            key={alert.id}
            initial={{ opacity: 0, x: 50, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 50, scale: 0.95 }}
            transition={{ duration: 0.2 }}
          >
            <Alert
              color={alertTypeToColor[alert.type]}
              variant="faded"
              title={alert.title}
              description={alert.message}
              isClosable
              onClose={() => removeAlert(alert.id)}
              endContent={
                alert.onRetry ? (
                  <Button
                    onClick={() => {
                      alert.onRetry?.();
                      removeAlert(alert.id);
                    }}
                    variant="bordered"
                    color={alertTypeToColor[alert.type]}
                    size="sm"
                  >
                    Retry
                  </Button>
                ) : undefined
              }
            />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

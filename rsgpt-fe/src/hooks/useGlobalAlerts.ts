'use client';

import { create } from 'zustand';

// Alert types that map to HeroUI Alert colors
export type AlertType = 'error' | 'warning' | 'success' | 'info';

export interface GlobalAlert {
  id: string;
  type: AlertType;
  title: string;
  message: string;
  timestamp: number;
  // Optional: action to retry
  onRetry?: () => void;
  // Auto-dismiss after this many ms (null = manual dismiss only)
  autoDismiss?: number | null;
}

interface GlobalAlertsState {
  alerts: GlobalAlert[];
  
  // Actions
  addAlert: (alert: Omit<GlobalAlert, 'id' | 'timestamp'>) => string;
  removeAlert: (id: string) => void;
  clearAllAlerts: () => void;
  
  // Convenience methods
  showError: (title: string, message: string, onRetry?: () => void) => string;
  showWarning: (title: string, message: string) => string;
  showSuccess: (title: string, message: string) => string;
  showInfo: (title: string, message: string) => string;
}

// Generate unique ID
function generateId(): string {
  return `alert-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

// Errors that should NOT trigger a global alert
// These are either handled elsewhere or are expected conditions
export const SILENT_ERRORS = [
  'Session expired',           // Handled by LogoutHandler
  'You are offline',           // Handled by NetworkStatus component
  'network_interrupted',       // Handled by NetworkInterruptionAlert in chat
  'Service temporarily unavailable', // Handled by circuit breaker UI
] as const;

// Check if an error message should be silent
export function shouldSilenceError(errorMessage: string): boolean {
  return SILENT_ERRORS.some(silent => 
    errorMessage.toLowerCase().includes(silent.toLowerCase())
  );
}

export const useGlobalAlerts = create<GlobalAlertsState>((set, get) => ({
  alerts: [],
  
  addAlert: (alertData) => {
    const id = generateId();
    const alert: GlobalAlert = {
      ...alertData,
      id,
      timestamp: Date.now(),
    };
    
    set((state) => ({
      alerts: [...state.alerts, alert],
    }));
    
    // Set up auto-dismiss if specified
    if (alertData.autoDismiss) {
      setTimeout(() => {
        get().removeAlert(id);
      }, alertData.autoDismiss);
    }
    
    return id;
  },
  
  removeAlert: (id) => {
    set((state) => ({
      alerts: state.alerts.filter((a) => a.id !== id),
    }));
  },
  
  clearAllAlerts: () => {
    set({ alerts: [] });
  },
  
  // Convenience methods
  showError: (title, message, onRetry) => {
    return get().addAlert({
      type: 'error',
      title,
      message,
      onRetry,
      autoDismiss: null, // Errors require manual dismiss
    });
  },
  
  showWarning: (title, message) => {
    return get().addAlert({
      type: 'warning',
      title,
      message,
      autoDismiss: 8000, // Warnings auto-dismiss after 8s
    });
  },
  
  showSuccess: (title, message) => {
    return get().addAlert({
      type: 'success',
      title,
      message,
      autoDismiss: 5000, // Success auto-dismiss after 5s
    });
  },
  
  showInfo: (title, message) => {
    return get().addAlert({
      type: 'info',
      title,
      message,
      autoDismiss: 6000, // Info auto-dismiss after 6s
    });
  },
}));

import React, { createContext, useCallback, useContext, useState } from 'react';

export interface ToastItem {
  id: string;
  title: string;
  body: string;
  urgency?: 'normal' | 'critical' | 'low';
  createdAt: number;
  exiting?: boolean;
}

interface ToastContextValue {
  toasts: ToastItem[];
  addToast: (options: { title: string; body: string; urgency?: 'normal' | 'critical' | 'low' }) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToasts(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToasts must be used within ToastProvider');
  return ctx;
}

const TOAST_DURATION_MS = 5000;
const TOAST_EXIT_MS = 200;

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const startExitToast = useCallback((id: string) => {
    setToasts((prev) =>
      prev.map((t) => (t.id === id ? { ...t, exiting: true } : t))
    );
    setTimeout(() => removeToast(id), TOAST_EXIT_MS);
  }, [removeToast]);

  const addToast = useCallback(
    (options: { title: string; body: string; urgency?: 'normal' | 'critical' | 'low' }) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      const item: ToastItem = {
        id,
        title: options.title,
        body: options.body,
        urgency: options.urgency ?? 'normal',
        createdAt: Date.now(),
      };
      setToasts((prev) => [...prev.slice(-4), item]);
      setTimeout(() => startExitToast(id), TOAST_DURATION_MS);
    },
    [startExitToast]
  );

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div
        className="fixed bottom-4 right-4 z-[99999] flex flex-col gap-2 pointer-events-none w-full max-w-sm"
        style={{ alignItems: 'flex-end' }}
        aria-live="polite"
      >
        {toasts.map((t) => (
          <ToastItemView key={t.id} item={t} />
        ))}
      </div>
    </ToastContext.Provider>
  );
};

const ToastItemView: React.FC<{ item: ToastItem }> = ({ item }) => {
  const isCritical = item.urgency === 'critical';
  const exitClass = item.exiting ? 'toast-exit' : 'toast-enter';
  return (
    <div
      role="alert"
      className={`${exitClass} pointer-events-auto rounded-lg border shadow-lg p-3 min-w-[200px] max-w-full`}
      style={{
        backgroundColor: 'var(--content1, #fff)',
        borderColor: isCritical ? 'var(--danger, #e11d48)' : 'var(--divider, #e5e5e5)',
        color: 'var(--foreground, #383838)',
      }}
    >
      <div className="font-semibold text-sm">{item.title}</div>
      {item.body && <div className="text-sm opacity-90 mt-0.5">{item.body}</div>}
    </div>
  );
};

'use client';

import { createContext, useContext, useState, ReactNode } from 'react';

interface SettingsModalContextType {
  isOpen: boolean;
  initialTab: string;
  openSettingsModal: (tab?: string) => void;
  closeSettingsModal: () => void;
}

const SettingsModalContext = createContext<SettingsModalContextType | undefined>(undefined);

export function SettingsModalProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [initialTab, setInitialTab] = useState('account-settings');

  const openSettingsModal = (tab: string = 'account-settings') => {
    setInitialTab(tab);
    setIsOpen(true);
  };

  const closeSettingsModal = () => {
    setIsOpen(false);
  };

  return (
    <SettingsModalContext.Provider value={{ isOpen, initialTab, openSettingsModal, closeSettingsModal }}>
      {children}
    </SettingsModalContext.Provider>
  );
}

export function useSettingsModal() {
  const context = useContext(SettingsModalContext);
  if (context === undefined) {
    throw new Error('useSettingsModal must be used within a SettingsModalProvider');
  }
  return context;
}

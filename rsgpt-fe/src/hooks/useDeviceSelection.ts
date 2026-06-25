'use client';

import { create } from 'zustand';

interface DeviceSelectionState {
  selectedDeviceId: string | null;
  setSelectedDeviceId: (deviceId: string | null) => void;
  clear: () => void;
}

export const useDeviceSelection = create<DeviceSelectionState>((set) => ({
  selectedDeviceId: null,
  setSelectedDeviceId: (deviceId: string | null) => set({ selectedDeviceId: deviceId }),
  clear: () => set({ selectedDeviceId: null }),
}));

// Export clear function for store-utils
export const clearDeviceSelection = () => {
  useDeviceSelection.getState().clear();
};


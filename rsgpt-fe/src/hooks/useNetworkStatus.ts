'use client';

import { create } from 'zustand';

// Type for queued actions
interface QueuedAction {
  id: string;
  action: () => Promise<void>;
  timestamp: number;
  description?: string;
}

interface NetworkStatusState {
  // Network status
  isOnline: boolean;
  wasOffline: boolean; // Track if we just came back online
  lastOfflineTime: number | null;
  
  // Action queue
  queuedActions: QueuedAction[];
  isFlushingQueue: boolean;
  
  // UI state - suppress offline alert when showing stream-specific error
  suppressOfflineAlert: boolean;
  
  // Actions
  setOnline: (online: boolean) => void;
  clearWasOffline: () => void;
  queueAction: (action: () => Promise<void>, description?: string) => string;
  removeQueuedAction: (id: string) => void;
  flushQueue: () => Promise<void>;
  clearQueue: () => void;
  setSuppressOfflineAlert: (suppress: boolean) => void;
}

// Generate unique ID for queued actions
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

export const useNetworkStatus = create<NetworkStatusState>((set, get) => ({
  // Initial state - assume online, check on mount
  isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
  wasOffline: false,
  lastOfflineTime: null,
  
  queuedActions: [],
  isFlushingQueue: false,
  
  // UI state
  suppressOfflineAlert: false,
  
  setOnline: (online: boolean) => {
    const currentState = get();
    
    if (online && !currentState.isOnline) {
      // Coming back online
      set({
        isOnline: true,
        wasOffline: true,
      });
      
      // Auto-flush queue when coming back online
      get().flushQueue();
    } else if (!online && currentState.isOnline) {
      // Going offline
      set({
        isOnline: false,
        lastOfflineTime: Date.now(),
      });
    }
  },
  
  clearWasOffline: () => {
    set({ wasOffline: false });
  },
  
  queueAction: (action: () => Promise<void>, description?: string) => {
    const id = generateId();
    const queuedAction: QueuedAction = {
      id,
      action,
      timestamp: Date.now(),
      description,
    };
    
    set((state) => ({
      queuedActions: [...state.queuedActions, queuedAction],
    }));
    
    return id;
  },
  
  removeQueuedAction: (id: string) => {
    set((state) => ({
      queuedActions: state.queuedActions.filter((a) => a.id !== id),
    }));
  },
  
  flushQueue: async () => {
    const state = get();
    
    // Don't flush if offline or already flushing
    if (!state.isOnline || state.isFlushingQueue || state.queuedActions.length === 0) {
      return;
    }
    
    set({ isFlushingQueue: true });
    
    const actionsToFlush = [...state.queuedActions];
    const failedActions: QueuedAction[] = [];
    
    for (const queuedAction of actionsToFlush) {
      try {
        await queuedAction.action();
        // Remove successful action from queue
        get().removeQueuedAction(queuedAction.id);
      } catch (error) {
        console.error(`Failed to execute queued action: ${queuedAction.description || queuedAction.id}`, error);
        // Keep failed action in queue for retry
        failedActions.push(queuedAction);
      }
    }
    
    set({ isFlushingQueue: false });
  },
  
  clearQueue: () => {
    set({ queuedActions: [] });
  },
  
  setSuppressOfflineAlert: (suppress: boolean) => {
    set({ suppressOfflineAlert: suppress });
  },
}));

// Initialize browser event listeners
if (typeof window !== 'undefined') {
  // Set initial state
  useNetworkStatus.setState({ isOnline: navigator.onLine });
  
  // Listen for online/offline events
  window.addEventListener('online', () => {
    useNetworkStatus.getState().setOnline(true);
    // Dispatch custom event for other parts of the app
    window.dispatchEvent(new CustomEvent('network-online'));
  });
  
  window.addEventListener('offline', () => {
    useNetworkStatus.getState().setOnline(false);
    // Dispatch custom event for other parts of the app
    window.dispatchEvent(new CustomEvent('network-offline'));
  });
}

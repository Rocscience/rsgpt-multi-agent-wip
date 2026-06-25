import { create } from 'zustand';

interface MessageInputState {
  position: 'center' | 'bottom' | 'hidden';
  disabled: boolean;
  onSubmit: ((text: string, sources: string[]) => void) | null;
  clearTextTrigger: number; // Increment to trigger text clearing
  initialText: string; // Text to pre-populate the input
  shouldAutoSend: boolean; // Trigger to auto-send the initial text
  setPosition: (position: 'center' | 'bottom' | 'hidden') => void;
  setDisabled: (disabled: boolean) => void;
  setOnSubmit: (onSubmit: (text: string, sources: string[]) => void) => void;
  clearText: () => void;
  setInitialText: (text: string) => void;
  triggerAutoSend: () => void; // Trigger auto-send on next render
  clear: () => void;
}

export const useMessageInputState = create<MessageInputState>((set, get) => ({
  position: 'center',
  disabled: false,
  onSubmit: null,
  clearTextTrigger: 0,
  initialText: '',
  shouldAutoSend: false,
  setPosition: (position) => set({ position }),
  setDisabled: (disabled) => set({ disabled }),
  setOnSubmit: (onSubmit) => set({ onSubmit }),
  clearText: () => set({ clearTextTrigger: get().clearTextTrigger + 1 }),
  setInitialText: (text) => {
    set({ initialText: text, shouldAutoSend: true });
  },
  triggerAutoSend: () => set({ shouldAutoSend: true }),
  clear: () => set({ position: 'center', disabled: false, onSubmit: null, clearTextTrigger: 0, initialText: '', shouldAutoSend: false }),
}));

// Export the store instance for clearing all stores on logout
export const clearMessageInputState = () => useMessageInputState.getState().clear();
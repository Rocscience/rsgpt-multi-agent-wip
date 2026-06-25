import { clearPendingMessage } from '@/hooks/usePendingFirstMessage';
import { clearMessageInputState } from '@/hooks/useMessageInputState';
import { clearModelSelection } from '@/hooks/useModelSelection';
import { clearAgentMode } from '@/hooks/useAgentMode';
import { clearDeviceSelection } from '@/hooks/useDeviceSelection';
import { clearContextUsage } from '@/hooks/useContextUsage';
import { useChatMessages } from '@/hooks/useChatMessages';

/**
 * Clears all Zustand stores on logout
 */
export function clearAllStores() {
  clearPendingMessage();
  clearMessageInputState();
  clearModelSelection();
  clearAgentMode();
  clearDeviceSelection();
  clearContextUsage();
  useChatMessages.getState().clear();
}

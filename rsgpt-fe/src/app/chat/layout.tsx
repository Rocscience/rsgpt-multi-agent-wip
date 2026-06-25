import ResponsiveSidebar from '@/components/side-bar/responsive-sidebar-wrapper';
import ResponsiveSourceList from '@/components/chat/sources/responsive-source-list';
import { MessageInput } from '@/components/chat/input/message-input';
import Link from 'next/link';
import { CitationHighlightProvider } from '@/contexts/CitationHighlightContext';
import { DeviceConnectionAlert } from '@/components/alerts/device-connection-alert';
import { DeviceTimeoutAlert } from '@/components/alerts/device-timeout-alert';
import { SettingsModalProvider } from '@/contexts/SettingsModalContext';
import { GlobalSettingsModal } from '@/components/side-bar/settings/global-settings-modal';
import { AgentModeBanner } from '@/components/banners/agent-mode-banner';

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return (
    <SettingsModalProvider>
      <CitationHighlightProvider>
        <div className="flex h-screen overflow-hidden">
          <ResponsiveSidebar />
          <main className="flex-1 overflow-y-auto bg-background h-screen relative min-w-0">
            <AgentModeBanner variant="chat" />
            <div className="h-full relative">
              {children}
              <MessageInput />
              <p className="absolute bottom-0 left-0 right-0 text-center text-xs text-default-600 pb-2 px-5 z-40">RSInsight may display inaccurate information, check its responses. Read our 
                <span className="underline text-xs ms-1"> 
                  <Link 
                    href='https://www.rocscience.com/about/rsinsight' 
                    className="underline text-xs" 
                    target="_blank"
                  >
                    Terms and Conditions
                  </Link>
                </span>.
              </p>
            </div>
          </main>
          <ResponsiveSourceList />
          <DeviceConnectionAlert />
          <DeviceTimeoutAlert />
          <GlobalSettingsModal />
        </div>
      </CitationHighlightProvider>
    </SettingsModalProvider>
  );
}
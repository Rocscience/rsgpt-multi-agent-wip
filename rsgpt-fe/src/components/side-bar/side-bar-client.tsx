// app/chat/SidebarClient.tsx
'use client'
import { useEffect, useState } from 'react';
import { SidebarHeader } from '@/components/side-bar/sidebar-header';
import { NewChatButton } from '@/components/side-bar/new-chat-button';
import { RSInsightDesktopButton } from '@/components/side-bar/rsinsight-desktop-button';
import { SessionList } from '@/components/side-bar/session-list';
import { Divider } from '@heroui/react';
import { SidebarUserProfile } from '@/components/side-bar/user-profile';
import { useGetUserSettings } from '@/hooks/useGetUserSettings';
import { useUser } from '@auth0/nextjs-auth0';

export default function SidebarClient() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { user } = useUser();
  const { data: userSettings } = useGetUserSettings(!!user);
  
  const isOptedIn = userSettings?.agent_mode_opt_in ?? false;

  useEffect(() => {
    // Component mounted
    return () => {
      // Component unmounted
    };
  }, []);

  return (
    <aside className={`bg-secondary hidden lg:flex flex-col h-screen overflow-hidden text-secondary-foreground transition-all duration-300 shrink-0 ${
      isCollapsed ? 'w-[60px]' : 'w-[260px] sm:w-[280px] lg:w-[300px]'
    }`}>
      <SidebarHeader isCollapsed={isCollapsed} onToggle={() => setIsCollapsed(v => !v)} />
      {!isCollapsed ? (
        <>
          <div className="p-2 flex-shrink-0 flex flex-col gap-1">
            <NewChatButton />
            {isOptedIn && <RSInsightDesktopButton />}
          </div>
          <Divider className="mx-2 flex-shrink-0 bg-default" />
          <div className="flex-1 overflow-y-auto p-2 pt-4 min-h-0 sidebar-scroll">
            <SessionList />
          </div>
          <Divider className="mx-2 flex-shrink-0 bg-default" />
        </>
      ) : (
        <>
          <div className="p-2 flex-shrink-0 flex flex-col items-center gap-1">
            <NewChatButton isCollapsed />
            {isOptedIn && <RSInsightDesktopButton isCollapsed />}
          </div>
        </>
      )}
      <div className={`${isCollapsed ? 'mt-auto p-2' : 'p-2 pt-0'}`}>
        <SidebarUserProfile isCollapsed={isCollapsed} />
      </div>
    </aside>
  );
}

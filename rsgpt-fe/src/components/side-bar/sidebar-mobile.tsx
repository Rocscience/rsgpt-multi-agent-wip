'use client'
import { useState } from 'react';
import { Button } from '@heroui/react';
import { Bars3Icon } from '@heroicons/react/24/outline';
import { SidebarHeader } from './sidebar-header';
import { NewChatButton } from './new-chat-button';
import { RSInsightDesktopButton } from './rsinsight-desktop-button';
import { SessionList } from './session-list';
import { Divider } from '@heroui/react';
import { SidebarUserProfile } from './user-profile';
import { useGetUserSettings } from '@/hooks/useGetUserSettings';
import { useUser } from '@auth0/nextjs-auth0';

export default function MobileSidebar() {
  const [isOpen, setIsOpen] = useState(false);
  const { user } = useUser();
  const { data: userSettings } = useGetUserSettings(!!user);
  
  const isOptedIn = userSettings?.agent_mode_opt_in ?? false;

  const toggleSidebar = () => setIsOpen(!isOpen);
  const closeSidebar = () => setIsOpen(false);

  return (
    <>
      {/* Hamburger Menu Button - Floating Top Left */}
      <Button
        isIconOnly
        variant="flat"
        className="fixed top-3 left-3 z-50 lg:hidden bg-secondary/80 backdrop-blur-sm border border-divider"
        onPress={toggleSidebar}
        aria-label="Open sidebar"
      >
        <Bars3Icon className="h-5 w-5" />
      </Button>

             {/* Mobile Drawer Overlay */}
       {isOpen && (
         <div 
           className="fixed inset-0 bg-default-100/50 z-40 lg:hidden"
           onClick={closeSidebar}
         />
       )}

       {/* Mobile Sidebar Drawer */}
       <aside className={`fixed top-0 left-0 flex flex-col h-screen w-[280px] bg-secondary overflow-hidden shadow-lg z-50 transform transition-transform duration-300 ease-in-out lg:hidden ${
         isOpen ? 'translate-x-0' : '-translate-x-full'
       }`}>
        <SidebarHeader isCollapsed={false} onToggle={() => {}} isMobile={true} closeSidebar={closeSidebar} />
        <div className="p-2 flex-shrink-0 flex flex-col gap-1">
          <NewChatButton isMobile={true} closeSidebar={closeSidebar} />
          {isOptedIn && <RSInsightDesktopButton />}
        </div>
        <Divider className="mx-2 flex-shrink-0 bg-default" />
        <div className="flex-1 overflow-y-auto p-2 pt-4 min-h-0 sidebar-scroll">
            <SessionList isMobile={true} closeSidebar={closeSidebar} />
        </div>
        <div className="p-2 pt-0">
            <SidebarUserProfile isCollapsed={false} />
        </div>
      </aside>
    </>
  );
}

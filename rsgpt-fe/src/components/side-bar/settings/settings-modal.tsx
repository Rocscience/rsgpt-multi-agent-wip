'use client';

import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button, Divider, Link, Tabs, Tab} from "@heroui/react";
import { useUser } from "@auth0/nextjs-auth0";
import { useState, useRef, useEffect } from "react";
import { ThemeSwitcher } from "@/components/side-bar/settings/theme-switcher";
import { AccountSettings } from "@/components/side-bar/settings/account-settings";
import { DeviceInfo } from "@/components/side-bar/settings/device-info";
import { DataConsent } from "@/components/side-bar/settings/data-consent";
import { useGetUserSettings } from "@/hooks/useGetUserSettings";

interface SettingsModalProps {
  organizationName: string;
  isOpen: boolean;
  onClose: () => void;
  initialTab?: string;
}

export function SettingsModal({ organizationName, isOpen, onClose, initialTab = "account-settings" }: SettingsModalProps) {
  const { user } = useUser();
  const { data: userSettings } = useGetUserSettings(!!user);
  
  const [activeTab, setActiveTab] = useState(initialTab);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const deviceRefetchRef = useRef<(() => void) | null>(null);

  // Update activeTab when initialTab changes (e.g., when opening from banner)
  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);

  const isOptedIn = userSettings?.agent_mode_opt_in ?? false;

  const handleDeviceRefetchReady = (refetch: () => void) => {
    deviceRefetchRef.current = refetch;
  };

  const handleRefreshDevices = async () => {
    if (deviceRefetchRef.current) {
      setIsRefreshing(true);
      try {
        await deviceRefetchRef.current();
      } finally {
        // Add a delay to show the animation
        setTimeout(() => setIsRefreshing(false), 1000);
      }
    }
  };

  const getFooterContent = () => {
    switch (activeTab) {
      case "account-settings":
        return (
          <Button as={Link} href="/auth/logout" color="default" variant="bordered">
            Log Out
          </Button>
        );
      case "device-info":
        return (
          <Button 
            color="primary" 
            variant="bordered" 
            onPress={handleRefreshDevices}
            isLoading={isRefreshing}
            disabled={isRefreshing}
          >
            Refresh
          </Button>
        );
      default:
        return null;
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl" className="p-4 min-h-[550px] max-h-[650px] transition-all duration-300" placement="center">
      <ModalContent>
        <ModalHeader className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <h1>Settings</h1>
            <ThemeSwitcher />
          </div>
        </ModalHeader>
        <ModalBody>
          <Tabs aria-label="Settings" selectedKey={activeTab} onSelectionChange={(key) => setActiveTab(key as string)}>
            <Tab key="account-settings" title="Account">
              <AccountSettings organizationName={organizationName} />
            </Tab>
            <Tab key="data-consent" title="Agent Mode">
              <DataConsent />
            </Tab>
            {isOptedIn && (
              <Tab key="device-info" title="Devices">
                <DeviceInfo onRefetchReady={handleDeviceRefetchReady} />
              </Tab>
            )}
          </Tabs>
        </ModalBody>
        <Divider />
        <ModalFooter>
          {getFooterContent()}
          {/* Close button */}
          <Button color="default" variant="flat" onPress={onClose}>
              Close
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
"use client";

import { useTheme } from "next-themes";
import { useEffect, useState, useCallback } from "react";
import { Button, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem, Tab } from "@heroui/react";
import { SunIcon, MoonIcon, ComputerDesktopIcon } from "@heroicons/react/24/outline";
import { useUpdateUserSettings } from "@/hooks/useUpdateUserSettings";
import { useGetUserSettings } from "@/hooks/useGetUserSettings";
import { useUser } from "@auth0/nextjs-auth0";

export function ThemeSwitcher() {
  const [mounted, setMounted] = useState(false);
  const { theme, setTheme } = useTheme();
  const { user } = useUser();
  const { data: userSettings } = useGetUserSettings(!!user);
  const { mutate: updateUserSettings } = useUpdateUserSettings();

  useEffect(() => {
    setMounted(true);
    // Add no-transition class temporarily to prevent flash on mount
    document.body.classList.add('no-transition');
    const timer = setTimeout(() => {
      document.body.classList.remove('no-transition');
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  const handleThemeChange = useCallback((selectedTheme: string) => {
    // Update local theme immediately
    setTheme(selectedTheme);
    
    // Persist to backend with current settings preserved
    // Use setTimeout to avoid blocking the UI update
    setTimeout(() => {
      updateUserSettings({
        theme: selectedTheme,
        preferred_sources: userSettings?.preferred_sources ?? ["ROC"],
        language: userSettings?.language ?? "English",
        timezone: userSettings?.timezone ?? "EST",
        agent_mode_opt_in: userSettings?.agent_mode_opt_in ?? false
      });
    }, 0);
  }, [setTheme, updateUserSettings, userSettings]);

  const getThemeIcon = () => {
    if (!mounted) return <ComputerDesktopIcon className="w-5 h-5" />;
    switch (theme) {
      case 'dark': return <MoonIcon className="w-5 h-5" />;
      case 'light': return <SunIcon className="w-5 h-5" />;
      default: return <ComputerDesktopIcon className="w-5 h-5" />;
    }
  };

  if (!mounted) return null;

  return (
      <Dropdown>
        <DropdownTrigger>
          <Button
            isIconOnly
            variant="ghost"
            size="sm"
            className="text-foreground hover:bg-muted"
            aria-label="Theme switcher"
          >
            {getThemeIcon()}
          </Button>
        </DropdownTrigger>
        <DropdownMenu 
          variant="light" 
          className="justify-end"
          onAction={(key) => handleThemeChange(key as string)}
        >
          <DropdownItem key="light" startContent={<SunIcon className="w-4 h-4" />}>
            Light
          </DropdownItem>
          <DropdownItem key="dark" startContent={<MoonIcon className="w-4 h-4" />}>
            Dark
          </DropdownItem>
          <DropdownItem key="system" startContent={<ComputerDesktopIcon className="w-4 h-4" />}>
            System
          </DropdownItem>
        </DropdownMenu>
      </Dropdown>
  );
}
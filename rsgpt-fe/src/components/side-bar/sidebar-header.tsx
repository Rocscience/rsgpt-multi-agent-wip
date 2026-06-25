'use client'
import { Button, Link, Tooltip } from "@heroui/react";
import Image from "next/image";
import { ChevronDoubleLeftIcon, XMarkIcon } from "@heroicons/react/24/outline";

// Collapse Icon Component
function CollapseIcon({ isCollapsed, className = "w-5 h-5" }: { isCollapsed: boolean; className?: string }) {
    return (
        <ChevronDoubleLeftIcon 
            className={`${className} transition-transform duration-300 ${isCollapsed ? 'rotate-180' : ''}`} 
        />
    );
}

interface SidebarHeaderProps {
    isCollapsed: boolean;
    onToggle: () => void;
    isMobile?: boolean;
    closeSidebar?: () => void;
}

// Sidebar Header Component
// Contains RSInsight logo, sidebar collapse button, and mobile menu exit button
export function SidebarHeader({ isCollapsed, onToggle, isMobile, closeSidebar }: SidebarHeaderProps) {
    if (isCollapsed) {
        return (
            <div className="flex flex-col items-center p-2">
                {/* Expand button that looks like logo by default, shows expand icon on hover */}
                <div className="group relative">
                    <Tooltip content="Expand sidebar" placement="right">
                        <Button
                            isIconOnly
                            color="default"
                            variant="light"
                            size="sm"
                            className="w-8 h-8 p-0 bg-transparent hover:bg-muted/70 transition-all duration-200"
                            aria-label="Expand sidebar"
                            onPress={onToggle}
                        >
                            {/* Show logo by default */}
                            <Image 
                                src="/images/logo_mark_rsinsight.svg" 
                                alt="RSInsight Logo" 
                                width={32} 
                                height={32}
                                className="group-hover:opacity-0 transition-opacity duration-200"
                            />
                            
                            {/* Show expand icon on hover */}
                            <CollapseIcon 
                                isCollapsed={isCollapsed} 
                                className="absolute inset-0 m-auto w-5 h-5 opacity-0 group-hover:opacity-100 transition-opacity duration-200" 
                            />
                        </Button>
                    </Tooltip>
                </div>
            </div>
        );
    }

    return (
        <div className="flex items-center justify-between p-2">
            {/* RSInsight Logo - Left side */}
            <Link href="/" className="flex items-center">
                <Image 
                    src="/images/logo_mark_rsinsight.svg" 
                    alt="RSInsight Logo" 
                    width={32} 
                    height={32}
                    className="hover:opacity-80 transition-opacity"
                />
            </Link>
            
            {/* Collapse Button - Right side */}
            <Tooltip content={isMobile ? "Close sidebar" : "Collapse sidebar"} placement="bottom">
                {isMobile ? (
                    <Button
                        isIconOnly
                        color="default"
                        variant="light"
                        size="sm"
                        className="bg-transparent hover:bg-muted/70"
                        aria-label="Close sidebar"
                        onPress={closeSidebar}
                    >
                        <XMarkIcon className="w-5 h-5" />
                    </Button>
                ) : (
                <Button
                    isIconOnly
                    color="default"
                    variant="light"
                    size="sm"
                    className="bg-transparent hover:bg-muted/70"
                    aria-label="Collapse sidebar"
                    onPress={onToggle}
                >
                    <CollapseIcon isCollapsed={isCollapsed} />
                </Button>
                )}
            </Tooltip>
        </div>
    );
}
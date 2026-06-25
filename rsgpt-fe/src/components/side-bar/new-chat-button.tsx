'use client'
import { Button, Tooltip } from "@heroui/react";
import NextLink from "next/link";
import { PencilSquareIcon } from "@heroicons/react/24/outline";
import { useNavigationState } from "@/hooks/useNavigationState";

// Pencil Icon Component


interface NewChatButtonProps {
    isCollapsed?: boolean;
    isMobile?: boolean;
    closeSidebar?: () => void;
}

// New Chat Button Component
// Displays a button to create a new chat session with a pencil icon
export function NewChatButton({ isCollapsed = false, isMobile = false, closeSidebar }: NewChatButtonProps) {
    const { setNavigating } = useNavigationState();

    const handleNewChatClick = () => {
        // Set navigation state immediately for visual feedback
        setNavigating(true, 'new');
        
        if (isMobile) {
            closeSidebar?.();
        }
    };
    if (isCollapsed) {
        return (
            <Tooltip content="New Chat" placement="right">
                <Button 
                    as={NextLink}
                    href="/chat"
                    isIconOnly
                    color="default" 
                    variant="light" 
                    className="bg-muted hover:bg-secondary/80"
                    aria-label="New Chat"
                    onPress={handleNewChatClick}
                >
                    <PencilSquareIcon className="w-5 h-5 text-foreground" />
                </Button>
            </Tooltip>
        );
    }

    return (
        <Button 
            as={NextLink}
            href="/chat"
            onPress={handleNewChatClick}
            color="default" 
            variant="light" 
            className="w-full justify-start hover:bg-secondary/80 text-foreground"
            startContent={<PencilSquareIcon className="w-5 h-5" />}
        >
            New Chat
        </Button>
    );
}

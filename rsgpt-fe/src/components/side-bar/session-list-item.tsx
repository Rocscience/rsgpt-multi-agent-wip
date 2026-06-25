'use client'

import { useState } from "react";
import { GetChatSessionMetaResponse } from "@/lib/types";
import { Button, Tooltip, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from "@heroui/react";
import { EllipsisHorizontalIcon, TrashIcon } from "@heroicons/react/24/outline";
import NextLink from "next/link";
import { useNavigationState } from "@/hooks/useNavigationState";
import { useDeleteSession } from "@/hooks/useDeleteSession";
import { DeleteSessionModal } from "./delete-session-modal";
import { useRouter } from "next/navigation";

// Session List Item Component
// Displays a single chat session with hover menu
export function SessionListItem({ 
    session, 
    isActive = false,
    isMobile = false,
    closeSidebar,
    currentSessionId
}: { 
    session: GetChatSessionMetaResponse;
    isActive?: boolean;
    isMobile?: boolean;
    closeSidebar?: () => void;
    currentSessionId?: string;
}) {
    const [isHovered, setIsHovered] = useState(false);
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const { setNavigating } = useNavigationState();
    const { mutate: deleteSession, isPending: isDeleting } = useDeleteSession();
    const router = useRouter();

    const handleSessionClick = () => {
        // Set navigation state immediately for visual feedback
        setNavigating(true, session.chat_session_id);
        
        if (isMobile) {
            closeSidebar?.();
        }
    };

    const handleDeleteClick = () => {
        setIsDeleteModalOpen(true);
    };

    const handleConfirmDelete = () => {
        deleteSession(session.chat_session_id, {
            onSuccess: () => {
                setIsDeleteModalOpen(false);
                // Only redirect if we're currently on the deleted session
                if (currentSessionId === session.chat_session_id) {
                    setNavigating(false);
                    router.push('/chat');
                }
            },
            onError: () => {
                // Modal stays open on error, user can retry or cancel
            }
        });
    };

    return (
        <>
            <Tooltip 
                content={session.title} 
                placement="right"
                delay={500}
            >
                <div 
                    className="relative"
                    onMouseEnter={() => setIsHovered(true)}
                    onMouseLeave={() => setIsHovered(false)}
                >
                    <Button
                        as={NextLink}
                        href={`/chat/${session.chat_session_id}`}
                        onPress={handleSessionClick}
                        color="default"
                        variant={isActive ? "solid" : "light"}
                        className={`w-full justify-start border-none pr-10 ${
                            isActive 
                                ? 'bg-default-300 shadow-sm' 
                                : 'bg-transparent hover:bg-default-300'
                        }`}
                    >
                        <span className="truncate">{session.title}</span>
                    </Button>
                    
                    {/* Three dots menu - visible on hover */}
                    <div 
                        className={`absolute right-1 top-1/2 -translate-y-1/2 transition-opacity duration-150 ${
                            isHovered ? 'opacity-100' : 'opacity-0'
                        }`}
                    >
                        <Dropdown placement="bottom-end">
                            <DropdownTrigger>
                                <Button
                                    isIconOnly
                                    size="sm"
                                    variant="light"
                                    className="min-w-6 w-6 h-6"
                                >
                                    <EllipsisHorizontalIcon className="w-4 h-4" />
                                </Button>
                            </DropdownTrigger>
                            <DropdownMenu aria-label="Session actions">
                                <DropdownItem
                                    key="delete"
                                    className="text-danger"
                                    color="danger"
                                    startContent={<TrashIcon className="w-4 h-4" />}
                                    onPress={handleDeleteClick}
                                >
                                    Delete
                                </DropdownItem>
                            </DropdownMenu>
                        </Dropdown>
                    </div>
                </div>
            </Tooltip>

            <DeleteSessionModal
                isOpen={isDeleteModalOpen}
                onClose={() => setIsDeleteModalOpen(false)}
                onConfirm={handleConfirmDelete}
                sessionTitle={session.title}
                isDeleting={isDeleting}
            />
        </>
    );
}

'use client'
import { AuthButtons } from "@/components/auth/auth-buttons";
import { RSInsightLogo } from "@/components/dashboard/rsinsight-logo";
import { getProxiedAvatarUrl } from "@/lib/avatar";
import { User } from "@auth0/nextjs-auth0/types";
import { Avatar, Button, Dropdown, DropdownItem, DropdownMenu, DropdownTrigger, Skeleton } from "@heroui/react";
import NextLink from "next/link";
import { useEffect, useState } from "react";

interface HeaderProps {
  user: User | null | undefined;
  rocPortalAccess: boolean | null;
  isLoading?: boolean;
}

// Header Component
// Displays the header with the logo, chat button, and user avatar if the user is logged in
export function Header({ user, rocPortalAccess, isLoading = false }: HeaderProps) {
    const [avatarLoading, setAvatarLoading] = useState(true);

    // Reset avatar loading state when user changes
    useEffect(() => {
        if (user?.picture) {
            setAvatarLoading(true);
        }
    }, [user?.picture]);

    return (
        <header className="max-w-full px-8 py-6 bg-background flex justify-between items-center relative sticky top-0 z-10">
            <NextLink href="/" className="absolute transform sm:left-0 md:left-1/2 md:-translate-x-1/2">
                {/* Full logo for larger screens */}
                <RSInsightLogo 
                    variant="full"
                    className="hidden sm:block w-40 text-foreground"
                />
                {/* Logo mark for small screens */}
                <RSInsightLogo 
                    variant="mark"
                    className="block sm:hidden w-10 h-10"
                />
            </NextLink>
            <div className="flex gap-4 items-center ml-auto">
                {isLoading ? (
                    // Loading skeleton while authentication status is being determined
                    <div className="flex gap-4 items-center">
                        <Skeleton className="h-10 w-16 rounded-lg" />
                        <Skeleton className="h-10 w-10 rounded-full" />
                    </div>
                ) : user ? (
                    <>
                        { rocPortalAccess !== false && (
                             <Button as={NextLink} href="/chat" color="primary" prefetch>Chat</Button>
                        )}
                        <Dropdown>
                            <DropdownTrigger>
                                {avatarLoading && user?.picture ? (
                                    <div className="relative">
                                        <Skeleton className="h-10 w-10 rounded-full" />
                                        <Avatar 
                                            src={getProxiedAvatarUrl(user.picture)} 
                                            className="absolute inset-0 opacity-0"
                                            imgProps={{
                                                onLoad: () => setAvatarLoading(false),
                                                onError: () => setAvatarLoading(false)
                                            }}
                                        />
                                    </div>
                                ) : (
                                    <Avatar 
                                        src={getProxiedAvatarUrl(user?.picture)} 
                                        imgProps={{
                                            onLoad: () => setAvatarLoading(false),
                                            onError: () => setAvatarLoading(false)
                                        }}
                                    />
                                )}
                            </DropdownTrigger>
                            <DropdownMenu variant="light" className="justify-end">
                                <DropdownItem key="logout" textValue="Logout">
                                    <AuthButtons user={user} />
                                </DropdownItem>
                            </DropdownMenu>
                        </Dropdown>
                    </>
                ) : (
                    <>
                        <AuthButtons user={user} />
                    </>
                )}
            </div>
        </header>
    );
}

'use client'

import { Button, Link } from "@heroui/react";
import { User } from "@auth0/nextjs-auth0/types";

interface AuthButtonsProps {
  user: User | null | undefined;
}

// Auth Buttons
// Displays a login button if the user is not logged in and a logout button if the user is logged in
export function AuthButtons({ user }: AuthButtonsProps) {
  if (!user) {
    return (
      <Button as={Link} 
        href="/auth/login" 
        color="primary"
      >
        Log in
      </Button>
    );
  }

  return (
    <Link 
      href="/auth/logout" 
      color="foreground"
      underline="hover"
    >
      Log out
    </Link>
  );
}
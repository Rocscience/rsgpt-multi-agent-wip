'use client';

import { Header } from "@/components/dashboard/header";

import AuthChecker from "@/components/auth/auth-checker";
import PromptAnimation from "@/components/dashboard/prompt-animation";
import { useEffect, useState } from "react";
import { useUser } from "@auth0/nextjs-auth0";
import { Button, Link } from "@heroui/react";
import { SettingsModalProvider } from "@/contexts/SettingsModalContext";
import { GlobalSettingsModal } from "@/components/side-bar/settings/global-settings-modal";
import { AgentModeBanner } from "@/components/banners/agent-mode-banner";


export default function Dashboard() {

  // Fetch the user session
  const { user, isLoading } = useUser();

  // Initialize to null to distinguish between "not yet determined" and "explicitly false"
  const [rocPortalAccess, setRocPortalAccess] = useState<boolean | null>(null);

  useEffect(() => {
    if (user) {
      // If user.rocPortalAccess is undefined, keep null to indicate "loading"
      // Otherwise, use the actual value (true or false)
      setRocPortalAccess(user.rocPortalAccess ?? null);
    }
  }, [user]);

  return (
    <SettingsModalProvider>
      <Header user={user} rocPortalAccess={rocPortalAccess} isLoading={isLoading} />
      <AgentModeBanner variant="dashboard" />
      {user && <AuthChecker user={user} isLoading={isLoading} rocPortalAccess={rocPortalAccess} setRocPortalAccess={setRocPortalAccess} />}
      <main className="overflow-y-hidden bg-secondary h-[calc(100vh-88px)] lg:pt-6 pt-16 flex flex-col items-center justify-center relative">

        <div className="flex flex-col items-center justify-center gap-4 px-3 sm:px-0 mt-6">
          <h1 className="text-2xl sm:text-4xl font-bold text-foreground max-w-lg text-center">Stop Digging for Answers, Just Use RSInsight</h1>
          <p className="text-secondary-foreground text-base sm:text-lg text-center">
            Fast and reliable data to back up your engineering decisions.
          </p>
          { user && !isLoading ? (
            <div className="flex flex-col items-center justify-center gap-4">
              <Button as={Link} 
                href="/chat"
                color="primary" 
                size="lg" 
                isDisabled={!user || isLoading || rocPortalAccess === false}
              >
                Ask a Question
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-4">
              <Button as={Link} href="/auth/login" color="primary" size="lg">Ask a Question</Button>
            </div>
          )}
        </div>
        <PromptAnimation />
      </main>
      <GlobalSettingsModal />
    </SettingsModalProvider>
  );
}
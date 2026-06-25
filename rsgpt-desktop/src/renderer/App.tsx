import React, { useEffect, useState } from 'react';
import { Button, Card, CardBody, CardHeader, Divider, Spinner, Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, useDisclosure } from '@heroui/react';
import { useToasts } from './components/ToastContainer';
import { useTheme } from 'next-themes';
import './globals.css';
import logoDark from './assets/images/rsinsight-plus-logo-dark.svg';
import logoLight from './assets/images/rsinsight-plus-logo-light.svg';
import { Dashboard } from './components/Dashboard';
import { AboutModal } from './components/AboutModal';
import { AutoUpdateBanner } from './components/AutoUpdateBanner';

const Logo: React.FC<{ className?: string }> = ({ className = '' }) => {
  const { theme, systemTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch by only rendering after mount
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div className={className} />;
  }

  const currentTheme = theme === 'system' ? systemTheme : theme;
  const logoSrc = currentTheme === 'dark' ? logoDark : logoLight;

  return <img src={logoSrc} alt="RSInsight" className={className} />;
};

const MCPStatusMonitor: React.FC = () => {
  const [lastStatus, setLastStatus] = useState<MCPStatusUpdate['status'] | null>(null);

  useEffect(() => {
    // Listen for MCP status updates
    const unsubscribe = window.electron.mcp.onStatus(async (status) => {
      console.log('[MCP Status]', status);

      // Only show notifications for status changes, not initial "starting" state
      if (lastStatus !== null && lastStatus !== status.status) {
        if (status.status === 'ready') {
          const listResponse = await window.electron.mcp.listTools();
          const tools = listResponse?.tools ?? {};
          const hasEnabledTools = Object.values(tools).some(
            (tool) => tool.exe_path && tool.enabled !== false
          );
          if (hasEnabledTools) {
            await window.electron.notification.show({
              title: 'Tools Ready',
              body: status.message,
              urgency: 'normal',
            });
          }
        } else if (status.status === 'error') {
          await window.electron.notification.show({
            title: 'Tool Error',
            body: status.message,
            urgency: 'critical',
          });
        }
      }

      setLastStatus(status.status);
    });

    // Get initial status
    window.electron.mcp.getStatus().then((status) => {
      if (status.ready) {
        setLastStatus('ready');
      } else if (status.error) {
        setLastStatus('error');
      } else {
        setLastStatus('starting');
      }
    });

    return unsubscribe;
  }, [lastStatus]);

  // This component doesn't render anything - it just monitors status and sends notifications
  return null;
};

/** Listens for notification:toast from main and shows in-app toasts (bottom-right). */
const ToastListener: React.FC = () => {
  const { addToast } = useToasts();
  useEffect(() => {
    const unsubscribe = window.electron.notification.onToast((options) => {
      addToast({
        title: options.title,
        body: options.body,
        urgency: options.urgency,
      });
    });
    return unsubscribe;
  }, [addToast]);
  return null;
};

const AppContent: React.FC = () => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [appVersion, setAppVersion] = useState<string>('');
  const { isOpen, onOpen, onClose } = useDisclosure();

  useEffect(() => {
    loadProfile();

    // Get app version
    window.electron.versions.getApp().then(setAppVersion);

    // Listen for session expiration events
    const cleanup = window.electron.auth.onSessionExpired(() => {
      console.log('Session expired, logging out...');
      setProfile(null);
      setLoading(false);
    });

    // Listen for About menu item click
    const unsubscribeAbout = window.electron.app.showAbout(() => {
      onOpen(); // Open the About modal
    });

    return () => {
      cleanup();
      unsubscribeAbout();
    };
  }, [onOpen]);

  const loadProfile = async () => {
    try {
      const userProfile = await window.electron.auth.getProfile();
      setProfile(userProfile);
    } catch (error) {
      console.error('Failed to load profile:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async () => {
    try {
      setLoading(true);
      const userProfile = await window.electron.auth.login();
      setProfile(userProfile);
    } catch (error) {
      console.error('Login failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    window.electron.auth.logOut();
  };

  if (!profile) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-default-100">
        <Card className="w-full max-w-md mx-4">
          <CardHeader className="flex flex-col gap-2 items-center pt-8 pb-4">
            <Logo className="h-12 w-auto mb-2" />
            <p className="text-default-500 text-center">
              Secure your session with Auth0 authentication
            </p>
          </CardHeader>
          <Divider />
          <CardBody className="flex flex-col items-center gap-4 py-8">
            {loading ? (
              <div className="flex flex-col items-center gap-3">
                <Spinner size="lg" color="primary" />
                <p className="text-default-500">Opening browser for authentication...</p>
              </div>
            ) : (
              <Button
                color="primary"
                size="lg"
                onClick={handleLogin}
                className="w-full max-w-xs"
              >
                Login with Auth0
              </Button>
            )}
          </CardBody>
        </Card>
        <MCPStatusMonitor />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <nav className="bg-content1 border-b border-divider">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Logo className="h-8 w-auto" />
            <Button
              className="bg-default-800 text-default-50"
              size="sm"
              onClick={handleLogout}
            >
              Logout
            </Button>
          </div>
        </div>
      </nav>
      <AutoUpdateBanner />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Dashboard profile={profile} />
      </div>
      <MCPStatusMonitor />

      <AboutModal isOpen={isOpen} onClose={onClose} appVersion={appVersion} />

    </div>
  );
};

const App: React.FC = () => {
  return (
    <>
      <AppContent />
      <ToastListener />
    </>
  );
};

export default App;

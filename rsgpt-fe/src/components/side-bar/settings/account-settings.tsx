'use client';

import { Button, Alert, Divider, Link } from "@heroui/react";
import { useUser } from "@auth0/nextjs-auth0";
import { useState } from "react";
import { useUpdateRocPortalStatus } from "@/hooks/useUpdateRocPortalStatus";

interface AccountSettingsProps {
    organizationName: string;
}
  
export function AccountSettings({ organizationName }: AccountSettingsProps) {
const { user } = useUser();
const { mutate: updateRocPortalStatus, isPending } = useUpdateRocPortalStatus();

const [syncStatus, setSyncStatus] = useState<'idle' | 'syncing' | 'success' | 'error'>('idle');

const handleRocPortalSync = async () => {
setSyncStatus('syncing');
updateRocPortalStatus(undefined, {
    onSuccess: () => {
    setSyncStatus('success');
    setTimeout(() => setSyncStatus('idle'), 3000);
    },
    onError: () => {
    setSyncStatus('error');
    setTimeout(() => setSyncStatus('idle'), 3000);
    }
});
};

const getSyncButtonText = () => {
    switch (syncStatus) {
    case 'syncing': return 'Syncing...';
    case 'success': return 'Sync Complete!';
    case 'error': return 'Sync Failed';
    default: return 'Sync Accounts';
    }
};

const getSyncButtonColor = () => {
    switch (syncStatus) {
    case 'syncing': return 'default';
    case 'success': return 'success';
    case 'error': return 'danger';
    default: return 'primary';
    }
};

const displayName = user?.name || user?.nickname || (user?.email ? user.email.split('@')[0] : 'User');
const hasRocPortalAccess = (user as unknown as { rocPortalAccess?: boolean })?.rocPortalAccess;

return (
    <div className="space-y-3">
        <div className="flex justify-between flex-wrap">
            <span className="text-foreground/70">Name:</span>
            <span className="font-medium">{displayName}</span>
        </div>
        <div className="flex justify-between flex-wrap">
            <span className="text-foreground/70">Email:</span>
            <span className="font-medium">{user?.email || 'Not available'}</span>
        </div>
        <Divider />
        <div className="flex justify-between">
            <span className="text-foreground/70">Organization:</span>
            <span className="font-medium">
                {organizationName || 'Not available'}
            </span>
        </div>
        <Divider />
        <div className="flex justify-between items-center">
            <span className="text-foreground/70">RocPortal Account:</span>
            <div className="flex justify-end">
                <Button
                color={getSyncButtonColor()}
                onPress={handleRocPortalSync}
                disabled={isPending}
                >
                {getSyncButtonText()}
                </Button>
            </div>
        </div>
        {!hasRocPortalAccess && (
            <Alert color="warning" variant="flat" title="Connect your RocPortal account to access RSInsight">
            </Alert>
        )}
    </div>
)}
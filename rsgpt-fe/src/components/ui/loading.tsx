'use client'

import { Spinner } from "@heroui/react";

// Checking User Permissions Loading Spinner
// Displays a loading spinner while checking the user's permissions
export function CheckingUserPermissions() {
    return (
        <div className="flex justify-center py-4 mb-4">
            <Spinner color="warning" label="Checking your permissions..." />
        </div>
    )
}
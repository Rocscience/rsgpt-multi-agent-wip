'use client';

import { Table, TableBody, TableCell, TableColumn, TableHeader, TableRow } from "@heroui/react";
import { useGetDeviceInfo } from "@/hooks/useGetDeviceInfo";

interface DeviceInfoProps {
    onRefetchReady?: (refetch: () => void) => void;
}

export function DeviceInfo({ onRefetchReady }: DeviceInfoProps) {
    const { data: deviceListResponse, refetch } = useGetDeviceInfo();
    
    // Expose the refetch function to parent component
    if (onRefetchReady) {
        onRefetchReady(refetch);
    }

    return (
        <Table removeWrapper className="overflow-y-auto">
            <TableHeader>
                <TableColumn>Device Name</TableColumn>
                <TableColumn>Device Type</TableColumn>
                <TableColumn>OS</TableColumn>
                <TableColumn>Last Active</TableColumn>
                <TableColumn>Status</TableColumn>
            </TableHeader>
            <TableBody emptyContent="No devices found">
                {deviceListResponse?.devices?.map((device) => (
                    <TableRow key={device.device_id}>
                        <TableCell>{device.device_name}</TableCell>
                        <TableCell>{device.device_type}</TableCell>
                        <TableCell>{device.os_name} {device.os_version}</TableCell>
                        <TableCell>{new Date(device.last_active).toLocaleDateString()}</TableCell>
                        <TableCell className={device.is_active ? 'text-green-500' : 'text-red-500'}>{device.is_active ? 'Active' : 'Inactive'}</TableCell>
                    </TableRow>
                )) || []}
            </TableBody>
        </Table>
    );
}
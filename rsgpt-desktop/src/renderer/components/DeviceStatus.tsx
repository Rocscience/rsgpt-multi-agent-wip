import React, { useEffect, useState } from 'react';
import { 
  Card, 
  CardBody, 
  CardHeader, 
  Divider, 
  Button,
  Chip,
  Tooltip,
  Spinner
} from '@heroui/react';

interface StatusInfo {
  device: DeviceStatus;
  websocket: WebSocketStatus;
  lastUpdate: Date;
}

export const DeviceStatusCard: React.FC = () => {
  const [statusInfo, setStatusInfo] = useState<StatusInfo | null>(null);
  const [reconnecting, setReconnecting] = useState({ device: false, websocket: false });

  useEffect(() => {
    loadStatus();
    
    // Set up device status change listener
    const cleanupDeviceStatus = window.electron.device.onStatusChanged(() => {
      console.log('Device status changed event received');
      loadStatus();
    });
    
    // Set up WebSocket event listeners
    const cleanupConnected = window.electron.websocket.onConnected(() => {
      console.log('WebSocket connected event received');
      loadStatus();
    });
    
    const cleanupDisconnected = window.electron.websocket.onDisconnected(() => {
      console.log('WebSocket disconnected event received');
      loadStatus();
    });

    // Refresh status every 30 seconds
    const interval = setInterval(loadStatus, 30000);

    return () => {
      cleanupDeviceStatus();
      cleanupConnected();
      cleanupDisconnected();
      clearInterval(interval);
    };
  }, []);

  const loadStatus = async () => {
    try {
      const [deviceStatus, websocketStatus] = await Promise.all([
        window.electron.device.getStatus(),
        window.electron.websocket.getStatus(),
      ]);

      setStatusInfo({
        device: deviceStatus,
        websocket: websocketStatus,
        lastUpdate: new Date(),
      });
    } catch (error) {
      console.error('Failed to load status:', error);
    }
  };

  const handleDeviceReconnect = async () => {
    setReconnecting({ ...reconnecting, device: true });
    try {
      const result = await window.electron.device.reconnect();
      if (result.success) {
        await loadStatus();
      } else {
        console.error('Device reconnect failed:', result.error);
      }
    } catch (error) {
      console.error('Device reconnect error:', error);
    } finally {
      setReconnecting({ ...reconnecting, device: false });
    }
  };

  const handleWebSocketReconnect = async () => {
    setReconnecting({ ...reconnecting, websocket: true });
    try {
      const result = await window.electron.websocket.reconnect();
      if (result.success) {
        await loadStatus();
      } else {
        console.error('WebSocket reconnect failed:', result.error);
      }
    } catch (error) {
      console.error('WebSocket reconnect error:', error);
    } finally {
      setReconnecting({ ...reconnecting, websocket: false });
    }
  };

  const formatOSInfo = (osName: string, osVersion: string): string => {
    const osMap: Record<string, string> = {
      darwin: 'macOS',
      win32: 'Windows',
      linux: 'Linux',
    };
    return `${osMap[osName] || osName} ${osVersion}`;
  };

  const getStatusColor = (isConnected: boolean): "success" | "danger" => {
    return isConnected ? 'success' : 'danger';
  };

  const formatLastUpdate = (date: Date): string => {
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  if (!statusInfo) {
    return (
      <Card className="shadow-md col-span-1 md:col-span-2">
        <CardBody>
          <div className="flex justify-center items-center py-12">
            <Spinner size="lg" color="primary" label="Loading status..." />
          </div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card className="shadow-md col-span-1 md:col-span-2">
      <CardHeader className="pb-3">
        <div className="flex flex-col w-full">
          <div className="flex justify-between items-center">
            <h3 className="text-xl font-semibold text-foreground">Device</h3>
            <span className="text-xs text-default-400">
              {formatLastUpdate(statusInfo.lastUpdate)}
            </span>
          </div>
        </div>
      </CardHeader>
      <Divider />
      <CardBody className="gap-4">
        {/* Device Registration Status */}
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className="text-sm text-default-600 font-medium">Device Registration</span>
          </div>
          <div className="flex items-center gap-2">
            <Chip
              color={getStatusColor(statusInfo.device.isRegistered)}
              variant="flat"
              size="sm"
            >
              {statusInfo.device.isRegistered ? 'Registered' : 'Not Registered'}
            </Chip>
            {!statusInfo.device.isRegistered && (
              <Button
                size="sm"
                color="secondary"
                variant="shadow"
                onClick={handleDeviceReconnect}
                isLoading={reconnecting.device}
              >
                Retry
              </Button>
            )}
          </div>
        </div>

        <Divider />

        {/* Device Connection Status (Web Socket) */}
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className="text-sm text-default-600 font-medium">Device Connection</span>
          </div>
          <div className="flex items-center gap-2">
            {!statusInfo.device.isRegistered ? (
              <Chip
                color="default"
                variant="flat"
                size="sm"
              >
                Unavailable
              </Chip>
            ) : (
              <>
                <Chip
                  color={getStatusColor(statusInfo.websocket.isConnected)}
                  variant="flat"
                  size="sm"
                >
                  {statusInfo.websocket.isConnected ? 'Connected' : 'Disconnected'}
                </Chip>
                {!statusInfo.websocket.isConnected && (
                  <Button
                    size="sm"
                    color="secondary"
                    variant="shadow"
                    onClick={handleWebSocketReconnect}
                    isLoading={reconnecting.websocket}
                  >
                    Retry
                  </Button>
                )}
              </>
            )}
          </div>
        </div>

        <Divider />

        {/* Device Info */}
        <div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm text-default-600 font-medium">Device Name</span>
            <div className="flex items-center gap-2">
              <span className="text-base text-foreground font-medium">
                {statusInfo.device.deviceName}
              </span>
              <Tooltip content={formatOSInfo(statusInfo.device.osName, statusInfo.device.osVersion)}>
                <Chip size="sm" variant="bordered" className="cursor-help">
                  {statusInfo.device.osName === 'darwin' ? 'macOS' : 
                   statusInfo.device.osName === 'win32' ? 'Windows' : 
                   statusInfo.device.osName}
                </Chip>
              </Tooltip>
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
};


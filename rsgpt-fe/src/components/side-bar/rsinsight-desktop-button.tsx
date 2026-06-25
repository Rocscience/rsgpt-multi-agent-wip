'use client'
import { Button, Tooltip } from "@heroui/react";
import { ComputerDesktopIcon, ArrowUpRightIcon } from "@heroicons/react/24/outline";

interface RSInsightDesktopButtonProps {
    isCollapsed?: boolean;
}

// RSInsight Desktop Button Component
// Opens the RSInsight Desktop application
export function RSInsightDesktopButton({ isCollapsed = false }: RSInsightDesktopButtonProps) {
    const handleOpenDesktopApp = () => {
        window.location.href = "com.rocscience.rsinsight://open";
    };

    if (isCollapsed) {
        return (
            <Tooltip content="RSInsight Desktop" placement="right">
                <Button 
                    isIconOnly
                    color="default" 
                    variant="light" 
                    className="bg-muted hover:bg-secondary/80"
                    aria-label="RSInsight Desktop"
                    onPress={handleOpenDesktopApp}
                >
                    <ComputerDesktopIcon className="w-5 h-5 text-foreground" />
                </Button>
            </Tooltip>
        );
    }

    return (
        <Button 
            onPress={handleOpenDesktopApp}
            color="default" 
            variant="light" 
            className="w-full hover:bg-secondary/80 text-foreground"
            startContent={<ComputerDesktopIcon className="w-5 h-5" />}
        >
            <span className="flex-1 text-left">RSInsight Desktop</span>
            <ArrowUpRightIcon className="w-4 h-4 text-foreground/60" />
        </Button>
    );
}

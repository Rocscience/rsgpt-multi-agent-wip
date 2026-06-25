'use client';

import { CircularProgress, Tooltip } from '@heroui/react';
import { useContextUsage } from '@/hooks/useContextUsage';

export const ContextUsageDisplay = () => {
  const { totalTokens, maxTokens, usagePercentage } = useContextUsage();

  // Don't render if no context usage yet
  if (totalTokens <= 0) {
    return null;
  }

  // Determine color based on usage percentage
  const getColor = () => {
    if (usagePercentage <= 70) return 'success';
    if (usagePercentage <= 85) return 'warning';
    return 'danger';
  };

  // Format numbers with K/M suffixes
  const formatNumber = (num: number): string => {
    if (num >= 1_000_000) {
      const millions = num / 1_000_000;
      const rounded = Math.round(millions * 10) / 10; // Round to 1 decimal
      return rounded % 1 === 0 ? `${Math.round(rounded)}M` : `${rounded}M`;
    }
    if (num >= 1_000) {
      const thousands = num / 1_000;
      const rounded = Math.round(thousands * 10) / 10; // Round to 1 decimal
      return rounded % 1 === 0 ? `${Math.round(rounded)}K` : `${rounded}K`;
    }
    return num.toString();
  };

  return (
    <Tooltip
      content={`${Math.round(usagePercentage)}% ∙ ${formatNumber(totalTokens)} / ${formatNumber(maxTokens)} context used`}
      placement="top"
      size="sm"
    >
      <div className="flex items-center ms-1">
        <CircularProgress
          size="sm"
          value={usagePercentage}
          color={getColor()}
          showValueLabel={true}
          strokeWidth={2}
          aria-label="Context usage"
          classNames={{
            svg: "w-8 h-8",
            value: "text-[0.65rem]"
          }}
        />
      </div>
    </Tooltip>
  );
};

ContextUsageDisplay.displayName = 'ContextUsageDisplay';


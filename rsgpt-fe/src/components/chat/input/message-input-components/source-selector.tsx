'use client';

import { Button, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem, Tooltip } from "@heroui/react";
import { CheckIcon } from '@heroicons/react/24/solid';
import { useTheme } from "next-themes";
import { SOURCE_LOGO_COMPONENTS } from './source-logos';

type Props = {
  selected: string[];
  onChange?: (sources: string[]) => void;
  readOnly?: boolean;
  isOpen?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
};

const ALL_SOURCES = [
  'ROC',
  'DIANA',
  '3GSM',
  '2SI',
  'ROCKFIELD',
  'AQUANTY',
];

// Mapping of source codes to full company names
const SOURCE_NAMES: Record<string, string> = {
  'ROC': 'Rocscience',
  'DIANA': 'DIANA',
  '3GSM': '3GSM',
  '2SI': '2Si',
  'ROCKFIELD': 'Rockfield',
  'AQUANTY': 'Aquanty',
};

// Mapping of source codes to company colors (light mode)
const SOURCE_COLORS: Record<string, string> = {
  'ROC': '#ED7433',
  'DIANA': '#0A3D3C',
  '3GSM': '#D6C13E',
  '2SI': '#2EB1CA',
  'ROCKFIELD': '#ee1e24',
  'AQUANTY': '#0068af',
};

// Mapping of source codes to company colors (dark mode)
const SOURCE_COLORS_DARK: Record<string, string> = {
  'ROC': '#ED7433',
  'DIANA': '#A8B8AD',
  '3GSM': '#D6C13E',
  '2SI': '#2EB1CA',
  'ROCKFIELD': '#ee1e24',
  'AQUANTY': '#0068af',
};

export function SourceSelector({ selected, onChange, readOnly, isOpen, onOpenChange }: Props) {
  const { theme } = useTheme();

  // Get the appropriate color mapping based on current theme
  const getSourceColors = () => {
    return theme === 'dark' ? SOURCE_COLORS_DARK : SOURCE_COLORS;
  };

  const handleSourceToggle = (sourceKey: React.Key) => {
    if (!onChange || readOnly) return;

    const source = sourceKey as string;
    const isCurrentlySelected = selected.includes(source);

    if (isCurrentlySelected) {
      // Prevent removing the last source (minimum 1 selected)
      if (selected.length === 1) return;
      // Remove from selection
      onChange(selected.filter(s => s !== source));
    } else {
      // Add to selection
      onChange([...selected, source]);
    }
  };

  // Render logos - shows 1 on mobile, up to 4 on desktop
  const renderLogos = () => {
    const sortedSelected = [...selected]
      .sort((a, b) => ALL_SOURCES.indexOf(a) - ALL_SOURCES.indexOf(b));
    
    const displaySources = sortedSelected.slice(0, 4);
    const mobileRemainingCount = sortedSelected.length - 1;
    const desktopRemainingCount = sortedSelected.length - 4;

    return (
      <div className="flex items-center -space-x-2 px-2">
        {displaySources.map((src, index) => {
          const LogoComponent = SOURCE_LOGO_COMPONENTS[src];
          // First logo always visible, logos 2-4 hidden on mobile (shown on sm+)
          const visibilityClass = index === 0 ? 'flex' : 'hidden sm:flex';
          
          return (
            <div
              key={src}
              className={`${visibilityClass} items-center justify-center bg-secondary rounded-2xl border-2 border-default-200 p-[0.35rem]`}
              style={{ zIndex: displaySources.length - index }}
            >
              <LogoComponent
                className="w-4 h-4 text-default-500"
              />
            </div>
          );
        })}
        {/* Mobile count badge - shows remaining after 1st logo */}
        {mobileRemainingCount > 0 && (
          <div 
            className="flex sm:hidden items-center justify-center bg-secondary rounded-2xl border-2 border-default-200 p-3 w-5 h-5"
            style={{ zIndex: 0 }}
          >
            <span className="text-[10px] font-medium text-default-500">+{mobileRemainingCount}</span>
          </div>
        )}
        {/* Desktop count badge - shows remaining after 4th logo */}
        {desktopRemainingCount > 0 && (
          <div 
            className="hidden sm:flex items-center justify-center bg-secondary rounded-2xl border-2 border-default-200 p-3 w-5 h-5"
            style={{ zIndex: 0 }}
          >
            <span className="text-[10px] font-medium text-default-500">+{desktopRemainingCount}</span>
          </div>
        )}
      </div>
    );
  };


  return (
      <div className="relative">
        <Dropdown 
          placement="bottom-end"
          size="sm"
          className="bg-background"
          isOpen={isOpen}
          onOpenChange={onOpenChange}
        >
          <DropdownTrigger>
          <Button
            variant="light"
            radius="full"
            size="sm"
            isDisabled={readOnly}
            aria-label="Source selector"
            className="text-default-500 flex-shrink-0 px-0 h-10 min-w-[40px]"
          >
          <Tooltip 
            content={`Sources: ${selected.map(s => SOURCE_NAMES[s]).join(', ')}`}
            placement="top"
            size="sm"
          >
            {renderLogos()}
          </Tooltip>
          </Button>
        </DropdownTrigger>
      <DropdownMenu 
        variant="light" 
        closeOnSelect={false}
        onAction={handleSourceToggle}
      >
        {ALL_SOURCES.map((src) => {
          const LogoComponent = SOURCE_LOGO_COMPONENTS[src];
          const isSelected = selected.includes(src);
          const sourceColor = getSourceColors()[src];

          return (
            <DropdownItem
              key={src}
              startContent={
                <LogoComponent
                  className="w-5 h-5"
                  style={{ color: isSelected ? sourceColor : 'currentColor' }}
                />
              }
              endContent={isSelected ? <CheckIcon className="w-4 h-4" /> : null}
            >
              <span className="text-xs font-medium">{SOURCE_NAMES[src]}</span>
            </DropdownItem>
          );
        })}
        </DropdownMenu>
        </Dropdown>
      </div>
  );
}


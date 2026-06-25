'use client';

import { 
  Button, 
  Divider,
  Spinner,
  Tooltip
} from '@heroui/react';
import { 
  MagnifyingGlassIcon, 
  XMarkIcon,
  LinkIcon
} from '@heroicons/react/24/outline';
import { useCitationHighlight } from '@/contexts/CitationHighlightContext';

interface SourceResult {
  title?: string;
  url?: string;
  date?: string;
  lastUpdated?: string;
  snippet?: string;
  source?: string;
}

interface SourceListProps {
  searchResults?: SourceResult[];
  isLoading?: boolean;
  isVisible?: boolean;
  onToggle?: () => void;
}

export function SourceList({ 
  searchResults, 
  isLoading = false, 
  isVisible = false,
  onToggle 
}: SourceListProps) {
  const { highlightedUrl, setHighlightedUrl } = useCitationHighlight();

  const results = searchResults ?? [];
  const hasResults = results.length > 0;

  const handleSourceClick = (url: string) => {
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const handleSourceHover = (url: string | null) => {
    setHighlightedUrl(url);
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return null;
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return dateString;
    }
  };

  return (
    <aside className="flex flex-col h-screen overflow-hidden text-secondary-foreground shrink-0 border-l border-default-100 w-full bg-background">
      {/* Header */}
      <div className="flex items-center justify-between p-3">
        <div className="flex items-center gap-2">
          <MagnifyingGlassIcon className="w-5 h-5" />
          <h3 className="font-semibold text-sm">Sources</h3>
          {hasResults && (
            <span className="text-xs text-default-500 bg-default-50 px-2 py-1 rounded-full">
              {results.length}
            </span>
          )}
        </div>
        
        {onToggle && (
          <Tooltip content="Close sources">
            <Button
              isIconOnly
              size="sm"
              variant="light"
              onPress={onToggle}
              className="text-default-500 hover:text-default-700"
            >
              <XMarkIcon className="w-4 h-4" />
            </Button>
          </Tooltip>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="flex flex-col items-center gap-3 text-default-500">
                <Spinner size="md" />
                <span className="text-sm">Searching for sources...</span>
              </div>
            </div>
           ) : hasResults ? (
             results.map((result, index) => (
               <Button
                 key={`${result.url || 'no-url'}-${index}`}
                 onPress={() => result.url && handleSourceClick(result.url)}
                 onMouseEnter={() => result.url && handleSourceHover(result.url)}
                 onMouseLeave={() => handleSourceHover(null)}
                 variant="light"
                 className={`w-full justify-start p-3 h-auto min-h-[120px] transition-colors ${
                   highlightedUrl === result.url ? 'bg-primary-50 border-primary-200' : ''
                 }`}
               >
                 <div className="flex flex-col items-start w-full space-y-2 text-left">
                   {/* Title */}
                   {result.title && (
                     <h4 className="font-medium text-sm text-foreground line-clamp-2 leading-tight w-full">
                       {result.title}
                     </h4>
                   )}
                   
                   {/* URL */}
                   {result.url && (
                     <div className="flex items-center gap-1 text-xs text-primary w-full">
                       <LinkIcon className="w-3 h-3 flex-shrink-0" />
                       <span className="truncate">{result.url}</span>
                     </div>
                   )}
                   
                   {/* Snippet */}
                   {result.snippet && (
                     <p className="text-xs text-default-600 line-clamp-3 leading-relaxed w-full">
                       {result.snippet}
                     </p>
                   )}
                   
                   {/* Metadata */}
                   {(result.date || result.lastUpdated || result.source) && (
                    <>
                      <Divider className="w-full" />
                      <div className="flex items-center gap-2 text-xs text-default-500 w-full">
                        {result.source && (
                          <span className="truncate">{result.source}</span>
                        )}
                        {(result.date || result.lastUpdated) && (
                          <span className="text-xs">
                            {formatDate(result.date || result.lastUpdated)}
                          </span>
                        )}
                      </div>
                     </>
                   )}
                 </div>
               </Button>
             ))
          ) : (
            <div className="text-center py-8 text-default-500">
              <MagnifyingGlassIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No sources found</p>
            </div>
          )}
      </div>
    </aside>
  );
}

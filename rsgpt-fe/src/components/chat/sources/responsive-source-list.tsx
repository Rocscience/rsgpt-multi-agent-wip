'use client';

import { useEffect, useState } from 'react';
import { Modal, ModalContent, ModalHeader, ModalBody, Button } from '@heroui/react';
import { MagnifyingGlassIcon, XMarkIcon, LinkIcon } from '@heroicons/react/24/outline';
import { SourceList } from './source-list';
import { useSourceList } from '@/hooks/useSourceList';
import { useCitationHighlight } from '@/contexts/CitationHighlightContext';

export default function ResponsiveSourceList() {
  const [isMobile, setIsMobile] = useState<boolean | null>(null);
  const { searchResults, isLoading, isVisible, toggleVisible, setVisible } = useSourceList();
  const { highlightedUrl, setHighlightedUrl } = useCitationHighlight();

  useEffect(() => {
    const checkScreenSize = () => {
      setIsMobile(window.innerWidth < 1024); // lg breakpoint
    };

    // Check on mount
    checkScreenSize();

    // Add event listener
    window.addEventListener('resize', checkScreenSize);

    // Cleanup
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  // Don't render until we've checked the screen size (prevents hydration mismatch)
  if (isMobile === null) {
    return null;
  }

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

  // Mobile: Render as modal
  if (isMobile) {
    return (
      <Modal 
        isOpen={isVisible} 
        onClose={() => setVisible(false)}
        size="xl"
        placement="center"
        scrollBehavior="inside"
      >
        <ModalContent>
          {(onClose) => (
            <>
              <ModalHeader className="flex items-center justify-between p-4 border-b border-default-100">
                <div className="flex items-center gap-2">
                  <MagnifyingGlassIcon className="w-5 h-5" />
                  <h3 className="font-semibold text-base">Sources</h3>
                  {hasResults && (
                    <span className="text-xs text-default-500 bg-default-50 px-2 py-1 rounded-full">
                      {results.length}
                    </span>
                  )}
                </div>
              </ModalHeader>
              <ModalBody>
                <div className="p-4 space-y-3">
                  {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="flex flex-col items-center gap-3 text-default-500">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                        <span className="text-sm">Searching for sources...</span>
                      </div>
                    </div>
                  ) : hasResults ? (
                    results.map((result, index) => (
                      <Button
                        key={`${result.url || 'no-url'}-${index}`}
                        onPress={() => result.url && handleSourceClick(result.url)}
                        variant="flat"
                        className="w-full justify-start p-4 h-auto min-h-[120px] bg-default-50"
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
                            <div className="flex items-center gap-2 text-xs text-default-500 w-full pt-2 border-t border-default-200">
                              {result.source && (
                                <span className="truncate">{result.source}</span>
                              )}
                              {(result.date || result.lastUpdated) && (
                                <span className="text-xs">
                                  {formatDate(result.date || result.lastUpdated)}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      </Button>
                    ))
                  ) : (
                    <div className="text-center py-12 text-default-500">
                      <MagnifyingGlassIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p className="text-sm">No sources found</p>
                    </div>
                  )}
                </div>
              </ModalBody>
            </>
          )}
        </ModalContent>
      </Modal>
    );
  }

  // Desktop: Render as sidebar
  return (
    <div 
      className={`overflow-hidden sidebar-transition ${
        isVisible ? 'w-[280px] sm:w-[300px] lg:w-[320px] xl:w-[450px]' : 'w-0'
      }`}
    >
      <SourceList
        searchResults={searchResults}
        isLoading={isLoading}
        isVisible={isVisible}
        onToggle={toggleVisible}
      />
    </div>
  );
}

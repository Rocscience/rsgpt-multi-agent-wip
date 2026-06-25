'use client';

import { useState, useEffect, useMemo } from 'react';
import { Button, Tooltip, Card, CardBody, Chip } from '@heroui/react';
import { HandThumbUpIcon, HandThumbDownIcon, ClipboardDocumentIcon, ClipboardDocumentCheckIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { HandThumbUpIcon as HandThumbUpSolidIcon, HandThumbDownIcon as HandThumbDownSolidIcon, MagnifyingGlassCircleIcon } from '@heroicons/react/24/solid';
import { useMessageFeedback } from '@/hooks/useMessageFeedback';
import { useSourceList } from '@/hooks/useSourceList';
import { MessageFeedbackRequest } from '@/lib/types';
import { ResponseInfo } from '../display/response-info';

type Props = {
  messageText: string;
  messageId: string;
  sessionId: string;
  onLike?: () => void;
  onDislike?: () => void;
  onCopy?: () => void;
  sourcesUsed?: string[];
  responseTimeMs?: number;
  tokenCount?: number;
  displayName?: string; // model name
  isAgentMode?: boolean;
  toolCount?: number;
  searchResults?: Array<{
    title?: string;
    url?: string;
    date?: string;
    lastUpdated?: string;
    snippet?: string;
    source?: string;
  }>;
};

const getFeedbackReasons = (feedbackType: 'like' | 'dislike'): { value: string; label: string }[] => {
  if (feedbackType === 'like') {
    return [
      { value: 'up_to_date', label: 'Up to date' },
      { value: 'accurate', label: 'Accurate' },
      { value: 'helpful', label: 'Helpful' },
      { value: 'followed_instructions', label: 'Followed instructions' },
      { value: 'relevant_sources', label: 'Relevant sources' },
      { value: 'other', label: 'Other...' }
    ];
  } else {
    return [
      { value: 'out_of_date', label: 'Out of date' },
      { value: 'inaccurate', label: 'Inaccurate' },
      { value: 'irrelevant_sources', label: 'Irrelevant sources' },
      { value: 'too_long', label: 'Too long' },
      { value: 'too_short', label: 'Too short' },
      { value: 'other', label: 'Other...' }
    ];
  }
};

export function UserFeedbackButtons({
  messageText,
  messageId,
  onLike,
  onDislike,
  onCopy,
  sourcesUsed,
  responseTimeMs,
  tokenCount,
  displayName,
  isAgentMode,
  searchResults,
  toolCount
}: Props) {
  const [isLiked, setIsLiked] = useState(false);
  const [isDisliked, setIsDisliked] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [showFeedbackReasons, setShowFeedbackReasons] = useState(false);
  const [pendingFeedbackType, setPendingFeedbackType] = useState<'like' | 'dislike' | null>(null);
  const [selectedReason, setSelectedReason] = useState<string | null>(null);
  const [description, setDescription] = useState('');
  
  const messageFeedbackMutation = useMessageFeedback();
  const { isVisible, toggleVisible, setSearchResults, searchResults: deduplicatedSources, activeMessageId, openSourcesForMessage, setVisible } = useSourceList();

  // Set search results in the source list context when they change
  useEffect(() => {
    if (searchResults && searchResults.length > 0) {
      setSearchResults(searchResults);
    }
  }, [searchResults, setSearchResults]);

  // Deduplicate search results for specific message (for button count)
  const messageDeduplicatedSources = useMemo(() => {
    if (!searchResults || searchResults.length === 0) return [];
    
    const seen = new Set<string>();
    return searchResults.filter(result => {
      if (!result.url || seen.has(result.url)) {
        return false;
      }
      seen.add(result.url);
      return true;
    });
  }, [searchResults]);

  const handleFeedbackClick = (feedbackType: 'like' | 'dislike') => {
    // If feedback is already submitted, don't allow changes
    if (isLiked || isDisliked) {
      return;
    }

    // Set the pending feedback type and show reasons
    setPendingFeedbackType(feedbackType);
    setShowFeedbackReasons(true);
    setSelectedReason(null);
    setDescription('');
  };

  const handleReasonSelect = (reason: string) => {
    setSelectedReason(reason);
    if (reason !== 'other') {
      // Auto-submit for non-other reasons using the button label as feedback_text
      const reasonData = getFeedbackReasons(pendingFeedbackType!).find(r => r.value === reason);
      handleFeedbackSubmit(reasonData?.label || reason);
    }
  };

  const handleFeedbackSubmit = async (customFeedbackText?: string) => {
    if (!pendingFeedbackType) return;

    // Use custom feedback text if provided, otherwise use selected reason label
    let feedbackText: string | undefined;
    if (customFeedbackText) {
      feedbackText = customFeedbackText;
    } else if (selectedReason && selectedReason !== 'other') {
      const reasonData = getFeedbackReasons(pendingFeedbackType).find(r => r.value === selectedReason);
      feedbackText = reasonData?.label;
    } else if (selectedReason === 'other' && description.trim()) {
      feedbackText = description.trim();
    }

    try {
      const body: MessageFeedbackRequest = {
        helpfulness_feedback: pendingFeedbackType === 'like', // true for like, false for dislike
        feedback_text: feedbackText,
      }
      
      await messageFeedbackMutation.mutateAsync({ messageId, body });

      // Update UI state - feedback is now locked in
      if (pendingFeedbackType === 'like') {
        setIsLiked(true);
        setIsDisliked(false);
        onLike?.();
      } else {
        setIsDisliked(true);
        setIsLiked(false);
        onDislike?.();
      }

      // Close feedback reasons and reset
      setShowFeedbackReasons(false);
      setPendingFeedbackType(null);
      setSelectedReason(null);
      setDescription('');
    } catch (error) {
      console.error('Failed to submit feedback:', error);
      // Don't update UI state on error
    }
  };

  const handleCloseFeedbackReasons = () => {
    setShowFeedbackReasons(false);
    setPendingFeedbackType(null);
    setSelectedReason(null);
    setDescription('');
  };

  const handleCopy = () => {
    // Generate special copy text: tool summary + clean message (no thinking)
    let copyText = messageText;

    if (toolCount && toolCount > 0) {
      const toolSummary = toolCount === 1 ? '[1 tool called]' : `[${toolCount} tools called]`;
      copyText = `${toolSummary}\n\n${copyText}`;
    }

    if (navigator.clipboard) {
        navigator.clipboard.writeText(copyText);
    }
    onCopy?.();

    // Show copied state temporarily
    setIsCopied(true);
    setTimeout(() => {
      setIsCopied(false);
    }, 2000); // Reset after 2 seconds
  };

  const handleSourcesClick = () => {
    if (!searchResults || searchResults.length === 0) {
      return;
    }

    // If sources list is already open
    if (isVisible) {
      // Scenario 1: Same source button is pressed - close the source list
      if (activeMessageId === messageId) {
        setVisible(false);
      } 
      // Scenario 2: Different source button is pressed - update to show new sources
      else {
        openSourcesForMessage(messageId, searchResults);
      }
    } 
    // If sources list is closed, open it with this message's sources
    else {
      openSourcesForMessage(messageId, searchResults);
    }
  };

  const feedbackReasons = pendingFeedbackType ? getFeedbackReasons(pendingFeedbackType) : [];

  return (
    <>
      <div className="flex items-center justify-between mt-3 pt-2 border-t border-secondary">
        <div className="flex items-center gap-2">
          {/* Only show like button if no feedback has been submitted */}
          {!isDisliked && (
            <Tooltip content={isLiked ? "Feedback submitted" : "Like this response"} placement="top">
              <Button
                size="sm"
                variant="light"
                isIconOnly
                className={`min-w-0 w-10 h-10 ${
                  isLiked 
                    ? 'text-primary cursor-not-allowed' 
                    : 'text-muted-foreground hover:bg-muted'
                }`}
                onPress={() => handleFeedbackClick('like')}
                aria-label={isLiked ? "Feedback submitted" : "Like this response"}
                isDisabled={isLiked || messageFeedbackMutation.isPending}
              >
                {isLiked ? (
                  <HandThumbUpSolidIcon className="w-4 h-4 text-primary" />
                ) : (
                  <HandThumbUpIcon className="w-4 h-4 text-muted-foreground" />
                )}
              </Button>
            </Tooltip>
          )}
          
          {/* Only show dislike button if no feedback has been submitted */}
          {!isLiked && (
            <Tooltip content={isDisliked ? "Feedback submitted" : "Dislike this response"} placement="top">
              <Button
                size="sm"
                variant="light"
                isIconOnly
                className={`min-w-0 w-10 h-10 ${
                  isDisliked 
                    ? 'text-destructive cursor-not-allowed' 
                    : 'text-muted-foreground hover:bg-muted'
                }`}
                onPress={() => handleFeedbackClick('dislike')}
                aria-label={isDisliked ? "Feedback submitted" : "Dislike this response"}
                isDisabled={isDisliked || messageFeedbackMutation.isPending}
              >
                {isDisliked ? (
                  <HandThumbDownSolidIcon className="w-4 h-4 text-destructive" />
                ) : (
                  <HandThumbDownIcon className="w-4 h-4 text-muted-foreground" />
                )}
              </Button>
            </Tooltip>
          )}
          
          <Tooltip content={isCopied ? "Response copied to clipboard" : "Copy response to clipboard"} placement="top">
            <Button
              size="sm"
              variant="light"
              isIconOnly
              className={`min-w-0 w-10 h-10 ${
                isCopied 
                  ? 'text-green-600 hover:text-green-700 hover:bg-green-50' 
                  : 'text-muted-foreground hover:bg-muted'
              }`}
              onPress={handleCopy}
              aria-label={isCopied ? "Response copied to clipboard" : "Copy response to clipboard"}
            >
              {isCopied ? (
                <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-600" />
              ) : (
                <ClipboardDocumentIcon className="w-4 h-4 text-muted-foreground" />
              )}
            </Button>
          </Tooltip>

          {/* Sources button */}
          {messageDeduplicatedSources.length > 0 && (
            <Chip as={Button}
              onPress={handleSourcesClick}
              aria-label="View sources"
              color="primary"
              size="sm"
              variant="light"
              startContent={<MagnifyingGlassCircleIcon className="w-5 h-5" />}
              className="text-xs text-primary hover:bg-primary/10"
            >
              {messageDeduplicatedSources.length} {messageDeduplicatedSources.length > 1 ? 'sources' : 'source'}
            </Chip>
          )}
        </div>
        
        {/* ResponseInfo on the right side */}
        <ResponseInfo 
          sourcesUsed={sourcesUsed}
          responseTimeMs={responseTimeMs}
          tokenCount={tokenCount}
          displayName={displayName}
          isAgentMode={isAgentMode}
        />
      </div>

      {showFeedbackReasons && (
        <Card className="mt-3 bg-default-200 border border-default-200">
          <CardBody className="p-4">
            <div className="flex justify-between items-start mb-3">
              <h3 className="text-md font-medium text-foreground">
                {pendingFeedbackType === 'like' ? 'What did you like?' : 'What could be improved?'}
              </h3>
              <Button
                size="sm"
                variant="light"
                isIconOnly
                className="min-w-0 w-6 h-6 text-muted-foreground hover:text-foreground"
                onPress={handleCloseFeedbackReasons}
                aria-label="Close feedback reasons"
              >
                <XMarkIcon className="w-4 h-4" />
              </Button>
            </div>

            {selectedReason === 'other' ? (
              <div className="space-y-3">
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="flat"
                    onPress={() => setSelectedReason(null)}
                    className="text-xs"
                  >
                    ← Back to reasons
                  </Button>
                </div>
                <div className="space-y-3">
                  <label className="text-sm font-medium text-foreground">
                    Please describe your feedback:
                  </label>
                  <textarea
                    placeholder="Tell us more about your feedback..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full p-2 mt-3 text-sm border bg-default-300 border-default-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                    rows={3}
                  />
                  <Button
                    size="sm"
                    color="primary"
                    onPress={() => handleFeedbackSubmit()}
                    isDisabled={!description.trim() || messageFeedbackMutation.isPending}
                    isLoading={messageFeedbackMutation.isPending}
                    className="float-right"
                  >
                    Submit
                  </Button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {feedbackReasons.map((reason) => (
                  <Button
                    key={reason.value}
                    size="sm"
                    variant="flat"
                    onPress={() => handleReasonSelect(reason.value)}
                    className="text-xs h-auto py-2 px-3 text-center justify-center"
                    isDisabled={messageFeedbackMutation.isPending}
                  >
                    {reason.label}
                  </Button>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      )}
    </>
  );
}

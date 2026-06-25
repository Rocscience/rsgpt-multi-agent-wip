import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import type { Components } from 'react-markdown';

type Props = {
  text: string;
  isStreaming: boolean;
  markdownComponents: Components;
  className?: string;
};

type ParagraphState = {
  id: string;
  content: string;
  hasAnimated: boolean;
  previousLength: number; // Track how much content we've already shown
};

/**
 * Component that tracks accumulated text and animates both paragraphs AND individual chunks as they stream.
 * 
 * Two-level animation system:
 * 1. Paragraph-level: New paragraphs fade in with a smooth 0.8s animation
 * 2. Chunk-level: Within each paragraph, newly arrived text chunks fade in with 0.8s animation
 * 
 * The key insight: during streaming, we receive the ENTIRE accumulated text on each render,
 * not just new chunks. We track what we've already shown (previousLength) and only animate
 * the difference, creating a smooth streaming experience without jarring text additions.
 */
export function AnimatedStreamingText({ 
  text, 
  isStreaming, 
  markdownComponents,
  className 
}: Props) {
  const [paragraphs, setParagraphs] = useState<ParagraphState[]>([]);
  const previousTextLengthRef = useRef<number>(0);
  const paragraphIdCounterRef = useRef<number>(0);

  useEffect(() => {
    // Reset when not streaming
    if (!isStreaming) {
      setParagraphs([]);
      previousTextLengthRef.current = 0;
      paragraphIdCounterRef.current = 0;
      return;
    }

    const currentLength = text.length;
    const previousLength = previousTextLengthRef.current;

    // Only process if new text has arrived
    if (currentLength <= previousLength) {
      return;
    }

    // Split entire text by paragraph boundaries
    const allParagraphs = text.split(/\n\n+/).filter(p => p.trim().length > 0);

    // Update paragraph states
    setParagraphs(currentParagraphs => {
      const newParagraphs: ParagraphState[] = [];
      
      allParagraphs.forEach((content, index) => {
        // Check if this paragraph already exists
        const existing = currentParagraphs[index];
        
        if (existing && existing.content === content) {
          // Paragraph unchanged, keep it as-is (update previousLength to current)
          newParagraphs.push({
            ...existing,
            previousLength: content.length
          });
        } else if (existing && content.startsWith(existing.content)) {
          // Paragraph is growing (still being typed) - keep the previous length for animation
          newParagraphs.push({
            ...existing,
            content,
            hasAnimated: existing.hasAnimated,
            // Don't update previousLength yet - we'll do that after animation
          });
        } else {
          // New paragraph or completely different content
          newParagraphs.push({
            id: existing?.id || `para-${paragraphIdCounterRef.current++}`,
            content,
            hasAnimated: existing?.hasAnimated || false,
            previousLength: 0 // New paragraph, nothing shown yet
          });
        }
      });

      return newParagraphs;
    });

    previousTextLengthRef.current = currentLength;
  }, [text, isStreaming]);

  // Mark paragraphs as animated and update previousLength after animation completes
  useEffect(() => {
    const timers: NodeJS.Timeout[] = [];
    
    paragraphs.forEach(paragraph => {
      // Update previousLength after a short delay to show chunk animation
      if (paragraph.content.length > paragraph.previousLength) {
        const timer = setTimeout(() => {
          setParagraphs(current => 
            current.map(p => 
              p.id === paragraph.id 
                ? { ...p, previousLength: p.content.length }
                : p
            )
          );
        }, 800); // Animation duration for chunks
        timers.push(timer);
      }
      
      // Mark paragraph as animated after paragraph fade completes
      if (!paragraph.hasAnimated) {
        const timer = setTimeout(() => {
          setParagraphs(current => 
            current.map(p => 
              p.id === paragraph.id ? { ...p, hasAnimated: true } : p
            )
          );
        }, 800); // Paragraph fade duration
        timers.push(timer);
      }
    });

    return () => {
      timers.forEach(timer => clearTimeout(timer));
    };
  }, [paragraphs.map(p => `${p.id}-${p.content.length}-${p.hasAnimated}`).join(',')]);

  // If not streaming, just render the full text normally
  if (!isStreaming) {
    return (
      <div className={className}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeKatex]}
          components={markdownComponents}
        >
          {text}
        </ReactMarkdown>
      </div>
    );
  }

  return (
    <div className={className}>
      {paragraphs.map((paragraph, index) => {
        // Animate paragraphs that haven't been animated yet
        const shouldAnimateParagraph = !paragraph.hasAnimated;
        
        // Split content into already-shown and newly-arrived chunks
        const alreadyShown = paragraph.content.slice(0, paragraph.previousLength);
        const newlyArrived = paragraph.content.slice(paragraph.previousLength);
        const hasNewContent = newlyArrived.length > 0;

        return (
          <motion.div
            key={shouldAnimateParagraph ? `${paragraph.id}-animating` : paragraph.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: shouldAnimateParagraph ? 0.8 : 0, ease: 'easeInOut' }}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[rehypeKatex]}
              components={markdownComponents}
            >
              {alreadyShown}
            </ReactMarkdown>
            {hasNewContent && (
              <motion.span
                key={`${paragraph.id}-chunk-${paragraph.previousLength}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
                style={{ display: 'inline' }}
              >
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={markdownComponents}
                >
                  {newlyArrived}
                </ReactMarkdown>
              </motion.span>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}


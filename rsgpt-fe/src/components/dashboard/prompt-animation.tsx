'use client';

import React from 'react';
import { Card, CardBody } from '@heroui/react';
import { ArrowRightIcon } from '@heroicons/react/24/outline';
import { motion, useMotionValue } from 'framer-motion';
import { useUser } from '@auth0/nextjs-auth0';
import { PROMPTS, PromptData } from '@/lib/consts';

interface PromptButtonProps {
  prompt: PromptData;
  onPress: (prompt: PromptData) => void;
  isDisabled?: boolean;
  isHighlighted?: boolean;
}

const PromptButton: React.FC<PromptButtonProps> = ({ prompt, onPress, isDisabled = false, isHighlighted = false }) => {
  return (
    <Card
      onPress={isDisabled ? undefined : () => onPress(prompt)}
      radius="md"
      shadow="none"
      isPressable={!isDisabled}
      isHoverable={!isDisabled}
      className={`${isHighlighted ? 'animated-border' : ''} text-secondary-foreground hover:text-foreground bg-default-200 flex-shrink-0 w-[400px] group ${isDisabled ? 'opacity-70 cursor-default hover:text-secondary-foreground' : ''}`}
    >
      <CardBody className="p-4">
        <div className="flex items-start gap-3 z-10 min-h-[60px]">
          <span className="leading-relaxed flex-1">
            {prompt.text}
          </span>
          <ArrowRightIcon className={`w-5 h-5 transition-transform duration-300 flex-shrink-0 mt-1 ${!isDisabled ? 'group-hover:translate-x-1' : ''}`} />
        </div>
      </CardBody>
    </Card>
  );
};

const PromptAnimation: React.FC = () => {
  // Fetch the user session and ROC portal access
  const { user, isLoading } = useUser();
  const [rocPortalAccess, setRocPortalAccess] = React.useState<boolean>(false);
  const [highlightedPromptIndices, setHighlightedPromptIndices] = React.useState<number[]>([]);
  const timeoutRefs = React.useRef<Set<NodeJS.Timeout>>(new Set());

  // Hover state for each row
  const [row1Hovered, setRow1Hovered] = React.useState(false);
  const [row2Hovered, setRow2Hovered] = React.useState(false);
  const [row3Hovered, setRow3Hovered] = React.useState(false);

  // Store the exact paused positions and animation start times
  const row1PausedPosition = React.useRef<number | null>(null);
  const row2PausedPosition = React.useRef<number | null>(null);
  const row3PausedPosition = React.useRef<number | null>(null);
  
  const row1StartTime = React.useRef<number>(Date.now());
  const row2StartTime = React.useRef<number>(Date.now());
  const row3StartTime = React.useRef<number>(Date.now());

  React.useEffect(() => {
    if (user) {
      setRocPortalAccess(user.rocPortalAccess);
    }
  }, [user]);

  // Cleanup effect for component unmount
  React.useEffect(() => {
    const timeouts = timeoutRefs.current;
    return () => {
      // Clear all pending timeouts on unmount
      timeouts.forEach(timeout => clearTimeout(timeout));
      timeouts.clear();
    };
  }, []);

  const prompts: PromptData[] = PROMPTS;

  const handlePromptClick = (prompt: PromptData) => {
    // Navigate to chat with prompt and sources in URL state
    const sourcesParam = prompt.sources.join(',');
    window.location.href = `/chat?prompt=${encodeURIComponent(prompt.text)}&sources=${encodeURIComponent(sourcesParam)}`;
  };

  // Check if prompts should be disabled
  const isDisabled = !user || isLoading || rocPortalAccess === false;

  // Helper function to check if a prompt should be highlighted
  const isPromptHighlighted = (originalIndex: number): boolean => {
    return highlightedPromptIndices.includes(originalIndex);
  };

  // Split prompts into 3 rows and duplicate them for seamless scrolling on large screens
  const row1Base = prompts.slice(0, 7);
  const row2Base = prompts.slice(7, 14);
  const row3Base = prompts.slice(14, 21);
  
  // Duplicate prompts multiple times to ensure smooth scrolling on large screens
  const duplicateCount = 2;
  const row1Prompts = Array(duplicateCount).fill(row1Base).flat();
  const row2Prompts = Array(duplicateCount).fill(row2Base).flat();
  const row3Prompts = Array(duplicateCount).fill(row3Base).flat();

  // Animation calculations for precise timing
  const cardWidth = 400; // Fixed width in pixels
  const gap = 16; // gap-4 = 16px
  const cardsPerRow = 7;
  const baseRowWidth = (cardWidth + gap) * cardsPerRow;
  const animationDuration = 80; // seconds for one complete cycle

  // Motion values to track current positions
  const row1X = useMotionValue(0);
  const row2X = useMotionValue(-baseRowWidth);
  const row3X = useMotionValue(100);

  // Animation control using direct motion value manipulation
  React.useEffect(() => {
    let animationFrame: number;
    
    const animate = () => {
      const now = Date.now();
      
      // Row 1: slides from 0 to -baseRowWidth
      if (!row1Hovered) {
        if (row1PausedPosition.current !== null) {
          // Resume from paused position - reset start time to account for pause duration
          row1StartTime.current = now - ((row1PausedPosition.current - 0) / (-baseRowWidth - 0)) * animationDuration * 1000;
          row1PausedPosition.current = null;
        }
        const elapsed = (now - row1StartTime.current) / 1000;
        const progress = (elapsed % animationDuration) / animationDuration;
        const currentX = 0 + (-baseRowWidth - 0) * progress;
        row1X.set(currentX);
      } else if (row1PausedPosition.current === null) {
        // Store the exact position when pausing
        row1PausedPosition.current = row1X.get();
      }
      
      // Row 2: slides from -baseRowWidth to 0
      if (!row2Hovered) {
        if (row2PausedPosition.current !== null) {
          // Resume from paused position - reset start time to account for pause duration
          row2StartTime.current = now - ((row2PausedPosition.current - (-baseRowWidth)) / (0 - (-baseRowWidth))) * animationDuration * 1000;
          row2PausedPosition.current = null;
        }
        const elapsed = (now - row2StartTime.current) / 1000;
        const progress = (elapsed % animationDuration) / animationDuration;
        const currentX = -baseRowWidth + (0 - (-baseRowWidth)) * progress;
        row2X.set(currentX);
      } else if (row2PausedPosition.current === null) {
        // Store the exact position when pausing
        row2PausedPosition.current = row2X.get();
      }
      
      // Row 3: slides from 100 to -baseRowWidth + 100
      if (!row3Hovered) {
        if (row3PausedPosition.current !== null) {
          // Resume from paused position - reset start time to account for pause duration
          row3StartTime.current = now - ((row3PausedPosition.current - 100) / ((-baseRowWidth + 100) - 100)) * animationDuration * 1000;
          row3PausedPosition.current = null;
        }
        const elapsed = (now - row3StartTime.current) / 1000;
        const progress = (elapsed % animationDuration) / animationDuration;
        const currentX = 100 + ((-baseRowWidth + 100) - 100) * progress;
        row3X.set(currentX);
      } else if (row3PausedPosition.current === null) {
        // Store the exact position when pausing
        row3PausedPosition.current = row3X.get();
      }
      
      animationFrame = requestAnimationFrame(animate);
    };
    
    animate();
    
    return () => {
      if (animationFrame) {
        cancelAnimationFrame(animationFrame);
      }
    };
  }, [row1Hovered, row2Hovered, row3Hovered, baseRowWidth, animationDuration, row1X, row2X, row3X]);

  // Add a new highlight every 3 seconds, each lasting 5 seconds for organic overlapping effect
  React.useEffect(() => {
    const timeouts = timeoutRefs.current;
    const interval = setInterval(() => {
      const totalPrompts = prompts.length;
      const randomIndex = Math.floor(Math.random() * totalPrompts);
      
      // Add the new highlight to existing ones (avoid duplicates)
      setHighlightedPromptIndices(prev => 
        prev.includes(randomIndex) ? prev : [...prev, randomIndex]
      );

      // Remove this specific highlight after 5.3 seconds
      const timeout = setTimeout(() => {
        setHighlightedPromptIndices(prev => prev.filter(index => index !== randomIndex));
        timeouts.delete(timeout);
      }, 5300);
      
      // Track timeout for cleanup
      timeouts.add(timeout);
    }, 3000); // Add new highlight every 3 seconds

    return () => {
      clearInterval(interval);
      // Clear all pending timeouts
      timeouts.forEach(timeout => clearTimeout(timeout));
      timeouts.clear();
    };
  }, [prompts.length]);


  return (
    <div className="w-full overflow-hidden py-8 bg-secondary">
      {/* Row 1 - Slides left */}
      <div 
        className="mb-2 overflow-hidden relative p-2"
        onMouseEnter={() => setRow1Hovered(true)}
        onMouseLeave={() => setRow1Hovered(false)}
      >
        <motion.div 
          className="flex gap-4 flex-nowrap"
          style={{ x: row1X }}
        >
            {row1Prompts.map((prompt, index) => {
             const originalIndex = index % row1Base.length; // Map back to original index in row1Base
             return (
               <PromptButton
                 key={`row1-${index}`}
                 prompt={prompt}
                 onPress={handlePromptClick}
                 isDisabled={isDisabled}
                 isHighlighted={isPromptHighlighted(originalIndex)}
               />
             );
           })}
        </motion.div>
        {/* Fade overlay for left and right edges */}
        <div className="absolute inset-y-0 left-0 w-10 sm:w-32 bg-gradient-to-r from-secondary to-transparent pointer-events-none z-10" />
        <div className="absolute inset-y-0 right-0 w-10 sm:w-32 bg-gradient-to-l from-secondary to-transparent pointer-events-none z-10" />
      </div>

      {/* Row 2 - Slides right */}
      <div 
        className="mb-2 overflow-hidden relative p-2"
        onMouseEnter={() => setRow2Hovered(true)}
        onMouseLeave={() => setRow2Hovered(false)}
      >
        <motion.div 
          className="flex gap-4 flex-nowrap"
          style={{ x: row2X }}
        >
            {row2Prompts.map((prompt, index) => {
             const originalIndex = 7 + (index % row2Base.length); // Map back to original index in row2Base
             return (
               <PromptButton
                 key={`row2-${index}`}
                 prompt={prompt}
                 onPress={handlePromptClick}
                 isDisabled={isDisabled}
                 isHighlighted={isPromptHighlighted(originalIndex)}
               />
             );
           })}
        </motion.div>
        {/* Fade overlay for left and right edges */}
        <div className="absolute inset-y-0 left-0 w-10 sm:w-32 bg-gradient-to-r from-secondary to-transparent pointer-events-none z-10" />
        <div className="absolute inset-y-0 right-0 w-10 sm:w-32 bg-gradient-to-l from-secondary to-transparent pointer-events-none z-10" />
      </div>

      {/* Row 3 - Slides left */}
      <div 
        className="mb-2 overflow-hidden relative p-2"
        onMouseEnter={() => setRow3Hovered(true)}
        onMouseLeave={() => setRow3Hovered(false)}
      >
        <motion.div 
          className="flex gap-4 flex-nowrap"
          style={{ x: row3X }}
        >
            {row3Prompts.map((prompt, index) => {
             const originalIndex = 14 + (index % row3Base.length); // Map back to original index in row3Base
             return (
               <PromptButton
                 key={`row3-${index}`}
                 prompt={prompt}
                 onPress={handlePromptClick}
                 isDisabled={isDisabled}
                 isHighlighted={isPromptHighlighted(originalIndex)}
               />
             );
           })}
        </motion.div>
        {/* Fade overlay for left and right edges */}
        <div className="absolute inset-y-0 left-0 w-10 sm:w-32 bg-gradient-to-r from-secondary to-transparent pointer-events-none z-10" />
        <div className="absolute inset-y-0 right-0 w-10 sm:w-32 bg-gradient-to-l from-secondary to-transparent pointer-events-none z-10" />
      </div>
    </div>
  );
};

export default PromptAnimation;

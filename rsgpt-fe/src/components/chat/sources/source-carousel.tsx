"use client";

import { useMemo, useRef, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Card, CardBody, Image, Button, Tooltip } from "@heroui/react";
import { ChevronLeftIcon, ChevronRightIcon } from "@heroicons/react/24/outline";
import type { MediaData } from "@/lib/types";


export type Props = {
  sources: MediaData;
  className?: string;
  cardSize?: { width: number; height: number };
  gap?: number;
};

export default function SourceCarousel({
  sources,
  className,
  cardSize = { width: 235, height: 160 },
  gap = 14,
}: Props) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);

  // Helper function to extract YouTube video ID
  const extractYouTubeVideoId = (url: string): string | null => {
    const patterns = [
      /(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/,
      /youtube\.com\/embed\/([^&\n?#]+)/,
      /youtube\.com\/v\/([^&\n?#]+)/
    ];

    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (match) return match[1];
    }
    return null;
  };

  const allMedia = useMemo(() => {
    const mediaItems: Array<{ type: 'image' | 'video', imageUrl?: string, sourceUrl?: string, videoUrl?: string, thumbnailUrl?: string, videoId?: string }> = [];

    // Add images (cap at 15 total)
    (sources.images ?? []).filter(Boolean).forEach((image) => {
      if (mediaItems.length < 15) {
        mediaItems.push({
          type: 'image',
          imageUrl: image.image_url,
          sourceUrl: image.source_url
        });
      }
    });

    // Add videos (YouTube URLs) - cap at 15 total
    (sources.videos ?? []).filter(Boolean).forEach((videoUrl) => {
      if (mediaItems.length < 15) {
        const videoId = extractYouTubeVideoId(videoUrl);
        if (videoId) {
          mediaItems.push({
            type: 'video',
            videoUrl,
            thumbnailUrl: `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`,
            videoId
          });
        }
      }
    });

    return mediaItems;
  }, [sources]);

  const onScroll = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const { scrollLeft, clientWidth, scrollWidth } = el;
    setAtStart(scrollLeft <= 2);
    setAtEnd(scrollLeft + clientWidth >= scrollWidth - 2);
  }, []);

  if (allMedia.length === 0) {
    return null;
  }

  const cardW = cardSize.width;
  const cardH = cardSize.height;

  const scrollByCards = (count: number) => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollBy({ left: count * (cardW + gap), behavior: "smooth" });
  };

  return (
    <motion.div 
      className={"mt-2 w-full relative " + (className ?? "") }
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.8, ease: 'easeInOut' }}
    >
      <div className="text-[10px] text-default-500 mb-1">Media found ({allMedia.length})</div>
      <div
        ref={scrollerRef}
        onScroll={onScroll}
        className="w-full overflow-x-auto scroll-smooth no-scrollbar snap-x snap-mandatory"
        style={{ gap }}
      >
        <div className="flex items-stretch pb-4" style={{ gap }}>
          {allMedia.map((item, i) => (
            <Card
              as="a"
              href={item.type === 'image' ? item.sourceUrl : item.videoUrl}
              target="_blank"
              rel="noopener noreferrer"
              key={i}
              className="shrink-0 snap-start shadow-sm rounded-2xl hover:shadow-md transition-shadow"
              style={{ width: cardW, minWidth: cardW, height: cardH }}
            >
              <CardBody className="p-0 h-full scroll-none overflow-hidden relative">
                {item.type === 'image' ? (
                  <Image
                    src={item.imageUrl}
                    alt={`Source image ${i + 1}`}
                    className="object-cover"
                    fallbackSrc="/images/placeholder.jpg"
                    radius="none"
                    style={{ width: cardW, minWidth: cardW, height: cardH }}
                    width={cardW}
                    height={cardH}
                  />
                ) : (
                  <>
                    <Image
                      src={item.thumbnailUrl}
                      alt={`YouTube video ${i + 1}`}
                      className="object-cover"
                      fallbackSrc="/images/placeholder.jpg"
                      radius="none"
                      style={{ width: cardW, minWidth: cardW, height: cardH }}
                      width={cardW}
                      height={cardH}
                    />
                    {/* Play button overlay for videos */}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="bg-black bg-opacity-50 rounded-full p-3">
                        <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5v14l11-7z"/>
                        </svg>
                      </div>
                    </div>
                  </>
                )}
              </CardBody>
            </Card>
          ))}
        </div>
      </div>

      {allMedia.length > 3 && (
        <>
          <Tooltip content="Previous" size="sm" placement="left">
            <Button
              isIconOnly
              size="md"
              variant="solid"
              radius="full"
              aria-label="Scroll previous"
              onPress={() => scrollByCards(-1)}
              className={`absolute -left-6 top-1/2 -translate-y-1/2 bg-secondary text-secondary-foreground z-10 ${
                atStart ? "opacity-40 pointer-events-none" : ""
              }`}
            >
              <ChevronLeftIcon className="h-5 w-5" />
            </Button>
          </Tooltip>

          <Tooltip content="Next" size="sm" placement="right">
            <Button
              isIconOnly
              size="md"
              variant="solid"
              radius="full"
              aria-label="Scroll next"
              onPress={() => scrollByCards(1)}
              className={`absolute -right-6 top-1/2 -translate-y-1/2 bg-secondary text-secondary-foreground z-10 ${
                atEnd ? "opacity-40 pointer-events-none" : ""
              }`}
            >
              <ChevronRightIcon className="h-5 w-5" />
            </Button>
          </Tooltip>
        </>
      )}
    </motion.div>
  );
}

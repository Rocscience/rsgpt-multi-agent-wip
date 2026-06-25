'use client'
import { useEffect, useState } from 'react';
import SidebarClient from './side-bar-client';
import MobileSidebar from './sidebar-mobile';

export default function ResponsiveSidebar() {
  const [isMobile, setIsMobile] = useState(false);

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

  // Render mobile sidebar for mobile devices
  if (isMobile) {
    return <MobileSidebar />;
  }

  // Render desktop sidebar for larger screens
  return <SidebarClient />;
}

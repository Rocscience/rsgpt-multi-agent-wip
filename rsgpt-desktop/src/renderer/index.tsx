import React from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider } from 'next-themes';
import { HeroUIProvider } from '@heroui/react';
import { ToastProvider } from './components/ToastContainer';
import App from './App';

const container = document.getElementById('root');
if (!container) {
  throw new Error('Root element not found');
}

const root = createRoot(container);
root.render(
  <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
    <HeroUIProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </HeroUIProvider>
  </ThemeProvider>
);

import '@tanstack/react-query';

// Extend React Query's meta types to include our custom fields
declare module '@tanstack/react-query' {
  interface Register {
    queryMeta: {
      /** Skip the global error handler entirely (no Sentry, no alert) */
      skipGlobalErrorHandler?: boolean;
      /** Show an error alert for query failures (queries are silent by default) */
      showErrorAlert?: boolean;
    };
    mutationMeta: {
      /** Skip the global error handler entirely (no Sentry, no alert) */
      skipGlobalErrorHandler?: boolean;
      /** Skip showing error alert but still log to Sentry (mutations show alerts by default) */
      skipErrorAlert?: boolean;
    };
  }
}

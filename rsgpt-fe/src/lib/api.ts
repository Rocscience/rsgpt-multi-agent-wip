import { API_PREFIX } from "./consts";
import { useNetworkStatus } from "@/hooks/useNetworkStatus";

// Circuit breaker state
const circuitBreakerState = {
  isOpen: false,
  failureCount: 0,
  lastFailureTime: 0,
  threshold: 5, // Open after 5 failures
  timeout: 30000, // 30 second cool-down
};

// Service health state
const serviceHealth = {
  isHealthy: true,
  lastCheck: 0,
  checkInterval: 30000, // Check every 30 seconds
};

/**
 * Check if browser is online
 */
function isBrowserOnline(): boolean {
  // Check Zustand store first, fallback to navigator.onLine
  if (typeof window !== 'undefined') {
    return useNetworkStatus.getState().isOnline;
  }
  return typeof navigator !== 'undefined' ? navigator.onLine : true;
}

/**
 * Open circuit breaker due to offline status
 */
export function openCircuitForOffline(): void {
  circuitBreakerState.isOpen = true;
  circuitBreakerState.lastFailureTime = Date.now();
}

/**
 * Reset circuit breaker when coming back online
 */
export function resetCircuitOnReconnect(): void {
  const wasOpen = circuitBreakerState.isOpen;
  circuitBreakerState.isOpen = false;
  circuitBreakerState.failureCount = 0;
  
  // Dispatch service recovered if circuit was open
  if (wasOpen && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('service-recovered'));
  }
}

/**
 * Check if circuit breaker should allow requests
 */
function canMakeRequest(): boolean {
  // If browser is offline, don't allow requests
  if (!isBrowserOnline()) {
    return false;
  }
  
  if (!circuitBreakerState.isOpen) return true;
  
  const now = Date.now();
  if (now - circuitBreakerState.lastFailureTime > circuitBreakerState.timeout) {
    // Reset circuit breaker
    circuitBreakerState.isOpen = false;
    circuitBreakerState.failureCount = 0;
    return true;
  }
  
  return false;
}

/**
 * Record a failure for circuit breaker
 */
function recordFailure(): void {
  circuitBreakerState.failureCount++;
  circuitBreakerState.lastFailureTime = Date.now();
  
  if (circuitBreakerState.failureCount >= circuitBreakerState.threshold) {
    circuitBreakerState.isOpen = true;
    // Dispatch event for UI to show service unavailable
    window.dispatchEvent(new CustomEvent('service-unavailable'));
  }
}

/**
 * Record a success for circuit breaker
 */
function recordSuccess(): void {
  const wasOpen = circuitBreakerState.isOpen;
  circuitBreakerState.failureCount = 0;
  circuitBreakerState.isOpen = false;
  
  // Only dispatch if circuit was previously open
  if (wasOpen) {
    window.dispatchEvent(new CustomEvent('service-recovered'));
  }
}

/**
 * Retry function with exponential backoff
 */
async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  retries: number = 2,
  baseDelay: number = 1000
): Promise<T> {
  for (let i = 0; i <= retries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (i === retries) throw error;
      
      // Only retry on network errors, not HTTP errors
      if (error instanceof TypeError && error.message.includes('fetch')) {
        const delay = baseDelay * Math.pow(2, i);
        await new Promise(resolve => setTimeout(resolve, delay));
      } else {
        throw error; // Don't retry HTTP errors
      }
    }
  }
  throw new Error('Retry failed');
}

/**
 * Fetch JSON data from the API with consistent headers and credentials.
 *
 * Enhanced with:
 * - Circuit breaker pattern
 * - Retry with exponential backoff for network errors
 * - Timeout handling
 * - Service health tracking
 * - Offline detection
 *
 * @template T
 * @param {string} path - Relative API path (should start with a `/`).
 * @param {RequestInit} [init] - Optional `fetch` configuration (method, headers, body, etc.).
 * @returns {Promise<T>} Parsed JSON response typed as `T`.
 * @throws {Error} If the response status is not OK, the error message contains the raw response text.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  // Check if browser is offline first
  if (!isBrowserOnline()) {
    throw new Error('You are offline. Please check your internet connection.');
  }
  
  // Check circuit breaker - completely block requests when circuit is open
  if (!canMakeRequest()) {
    // Don't make any requests during outage
    throw new Error('Service temporarily unavailable. Please try again later.');
  }

  const isGET = !init?.method || init.method === 'GET';
  
  const fetchFn = async () => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
    
    try {
      const res = await fetch(`${API_PREFIX}${path}`, {
        ...init,
        headers: {
          'Content-Type': 'application/json',
          ...(init?.headers ?? {}),
        },
        credentials: 'include',
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        const errorText = await res.text();

        if (res.status === 401) {
          // Trigger the LogoutHandler cleanup
          window.dispatchEvent(new Event('session-expired'));
          throw new Error('Session expired');
        }
        
        // Handle 503 Service Unavailable
        if (res.status === 503) {
          recordFailure();
          throw new Error('Service temporarily unavailable. Please try again later.');
        }

        if (res.status === 404) {
          throw new Error('Resource not found');
        }
        
        throw new Error(errorText);
      }

      recordSuccess();
      return res.json() as Promise<T>;
    } catch (error) {
      clearTimeout(timeoutId);
      
      // Network/timeout errors
      if (error instanceof TypeError || (error && typeof error === 'object' && 'name' in error && error.name === 'AbortError')) {
        recordFailure();
        throw new Error('Service temporarily unavailable. Please try again later.');
      }
      
      throw error;
    }
  };

  // Retry only for GET requests
  if (isGET) {
    return retryWithBackoff(fetchFn);
  } else {
    return fetchFn();
  }
}

/**
 * Check service health - bypasses circuit breaker to always check
 * Skips health check if browser is offline to save bandwidth
 */
export async function checkServiceHealth(): Promise<boolean> {
  // Skip health check if browser is offline
  if (!isBrowserOnline()) {
    serviceHealth.isHealthy = false;
    return false;
  }
  
  const now = Date.now();
  if (now - serviceHealth.lastCheck < serviceHealth.checkInterval) {
    return serviceHealth.isHealthy;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    
    // Health check bypasses circuit breaker to always attempt connection
    const res = await fetch(`${API_PREFIX}/health`, {
      signal: controller.signal,
      cache: 'no-store',
    });
    
    clearTimeout(timeoutId);
    
    const wasHealthy = serviceHealth.isHealthy;
    serviceHealth.isHealthy = res.ok;
    serviceHealth.lastCheck = now;
    
    // If service recovered, reset circuit breaker
    if (!wasHealthy && serviceHealth.isHealthy) {
      circuitBreakerState.isOpen = false;
      circuitBreakerState.failureCount = 0;
      window.dispatchEvent(new CustomEvent('service-recovered'));
    } else if (wasHealthy && !serviceHealth.isHealthy) {
      window.dispatchEvent(new CustomEvent('service-unavailable'));
    }
    
    return serviceHealth.isHealthy;
  } catch (error) {
    serviceHealth.isHealthy = false;
    serviceHealth.lastCheck = now;

    // Only dispatch event if this is a state change
    if (serviceHealth.isHealthy) {
      window.dispatchEvent(new CustomEvent('service-unavailable'));
    }
    
    return false;
  }
}

/**
 * Queue an action to be retried when back online.
 * Use this for critical actions that should not be lost (e.g., feedback submission).
 * 
 * @param action - The async function to queue
 * @param description - Optional description for debugging
 * @returns The queued action ID
 */
export function queueActionForRetry(
  action: () => Promise<void>,
  description?: string
): string {
  return useNetworkStatus.getState().queueAction(action, description);
}

/**
 * Remove a queued action by ID
 */
export function removeQueuedAction(id: string): void {
  useNetworkStatus.getState().removeQueuedAction(id);
}

/**
 * Get the number of queued actions
 */
export function getQueuedActionsCount(): number {
  return useNetworkStatus.getState().queuedActions.length;
}

// Listen for network status changes to manage circuit breaker
if (typeof window !== 'undefined') {
  window.addEventListener('network-offline', () => {
    openCircuitForOffline();
  });
  
  window.addEventListener('network-online', () => {
    resetCircuitOnReconnect();
    // Trigger a health check when coming back online
    checkServiceHealth();
  });
}

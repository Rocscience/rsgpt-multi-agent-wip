import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
import { getAccessToken } from './authService';
import { config } from '../config/environment';
import { BrowserWindow } from 'electron';


// Import types from mcpService
export interface MCPRegistryListResponse {
    mcps: Array<{
        id: string;
        name: string;
        display_name: string;
        description?: string;
        category?: string;
        author?: string;
        latest_version: string;
        downloads_count: number;
        is_official: boolean;
    }>;
    total: number;
    page: number;
    pages: number;
}

export interface MCPDownloadResponse {
    download_url: string;
    checksum_sha256?: string;
    filename: string;
    size_bytes?: number;
}

// Circuit breaker state
const circuitBreakerState = {
    isOpen: false,
    failureCount: 0,
    lastFailureTime: 0,
    threshold: 5, // Open after 5 failures
    timeout: 30000, // 30 second cool-down
};

export class ApiFetchService {
    private apiClient: AxiosInstance;
    private baseURL: string;

    constructor() {
        this.baseURL = config.API_BASE_URL;
        this.apiClient = this.createAPIClient();
    }

    private createAPIClient(): AxiosInstance {
        const client = axios.create({
            baseURL: this.baseURL,
            timeout: 15000,
        });

        // Request interceptor to add auth headers
        client.interceptors.request.use(
            (config) => {
                const token = getAccessToken();
                if (token) {
                    config.headers.Authorization = `Bearer ${token}`;
                }
                return config;
            },
            (error) => {
                return Promise.reject(error);
            }
        );

        // Response interceptor for error handling
        client.interceptors.response.use(
            (response) => {
                // Record success for circuit breaker
                this.recordSuccess();
                return response;
            },
            (error) => {
                const status = error.response?.status;
                // Only trip the breaker for 5xx or network/timeout errors
                if (!status || status >= 500) {
                    this.recordFailure();
                }
                // Keep AxiosError but clarify message
                if (status === 401) {
                    // Notify renderer process that session has expired
                    const mainWindow = BrowserWindow.getAllWindows()[0];
                    if (mainWindow) {
                        mainWindow.webContents.send('auth:session-expired');
                    }
                    return Promise.reject(Object.assign(error, { message: 'Session expired' }));
                }
                if (status === 503) {
                    return Promise.reject(Object.assign(error, { message: 'Service temporarily unavailable. Please try again later.' }));
                }
                return Promise.reject(error);
            }
        );
        return client;
    }

    /**
     * Check if circuit breaker should allow requests
     */
    private canMakeRequest(): boolean {
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
    private recordFailure(): void {
        circuitBreakerState.failureCount++;
        circuitBreakerState.lastFailureTime = Date.now();
        
        if (circuitBreakerState.failureCount >= circuitBreakerState.threshold) {
            circuitBreakerState.isOpen = true;
        }
    }

    /**
     * Record a success for circuit breaker
     */
    private recordSuccess(): void {
        circuitBreakerState.failureCount = 0;
        circuitBreakerState.isOpen = false;
    }

    /**
     * Retry function with exponential backoff 
     */
    private async retryWithBackoff<T>(
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
                if (error instanceof TypeError || (error as any)?.code === 'ECONNABORTED') {
                    const delay = baseDelay * Math.pow(2, i);
                    await new Promise(resolve => setTimeout(resolve, delay));
                } else {
                    throw error; // Don't retry HTTP errors
                }
            }
        }
        throw new Error('Retry failed');
    }

    // Generic GET method with circuit breaker and retry
    async get<T>(endpoint: string, config?: AxiosRequestConfig): Promise<T> {
        // Check circuit breaker
        if (!this.canMakeRequest()) {
            throw new Error('Service temporarily unavailable. Please try again later.');
        }

        const isGET = !config?.method || config.method === 'GET';
        
        const fetchFn = async () => {
            const response = await this.apiClient.get<T>(endpoint, config);
            return response.data;
        };

        // Retry only for GET requests
        if (isGET) {
            return this.retryWithBackoff(fetchFn);
        } else {
            return fetchFn();
        }
    }

    // Generic POST method
    async post<T>(endpoint: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
        if (!this.canMakeRequest()) {
            throw new Error('Service temporarily unavailable. Please try again later.');
        }

        const response = await this.apiClient.post<T>(endpoint, data, config);
        return response.data;
    }

    // Generic PUT method
    async put<T>(endpoint: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
        if (!this.canMakeRequest()) {
            throw new Error('Service temporarily unavailable. Please try again later.');
        }

        const response = await this.apiClient.put<T>(endpoint, data, config);
        return response.data;
    }

    // Generic DELETE method
    async delete<T>(endpoint: string, config?: AxiosRequestConfig): Promise<T> {
        if (!this.canMakeRequest()) {
            throw new Error('Service temporarily unavailable. Please try again later.');
        }

        const response = await this.apiClient.delete<T>(endpoint, config);
        return response.data;
    }
    
    // MCP-specific methods
    async fetchMCPRegistry(params?: { page?: number; limit?: number; official_only?: boolean}): Promise<MCPRegistryListResponse> {
        return this.get<MCPRegistryListResponse>('/mcp/registry/list', { params });
    }
    
    async fetchMCPDownloadInfo(toolId: string, version?: string): Promise<MCPDownloadResponse> {
        const safeId = encodeURIComponent(toolId);
        const safeVer = version ? encodeURIComponent(version) : undefined;
        const endpoint = safeVer
            ? `/mcp/registry/download/${safeId}/${safeVer}`
            : `/mcp/registry/download/${safeId}`;
        return this.get<MCPDownloadResponse>(endpoint);
    }

    async logMCPInstall(mcpId: string, version: string, deviceId: string, action: 'install' | 'update' | 'uninstall'): Promise<void> {
        //Uses JWT auth (automatically added by interceptor) instead of X-Service-Token
        return this.post<void>('/mcp/registry/install-log', {
            mcp_id: mcpId,
            version: version,
            device_id: deviceId,
            action: action
        });
    }

}

export const apiFetchService = new ApiFetchService();

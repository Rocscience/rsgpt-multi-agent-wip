/**
 * Session Service - In-memory storage for MCP service tokens
 *
 * Manages MCP tokens fetched from the backend after Auth0 login.
 * Tokens are stored in memory only (not persisted to disk) for security.
 *
 * Security Model:
 * - MCP tokens are fetched from backend using JWT authentication
 * - Desktop uses JWT directly for backend API calls (no desktop token needed)
 * - Tokens are cleared on logout
 * - No disk persistence - tokens only live in application memory
 */

interface MCPCredential {
  token: string;
}

interface ServiceTokens {
  mcp_credentials: {
    [key: string]: MCPCredential;
  };
}

class SessionService {
  private serviceTokens: ServiceTokens | null = null;

  /**
   * Store MCP service tokens in memory
   */
  setServiceTokens(tokens: ServiceTokens): void {
    this.serviceTokens = tokens;
    console.log('✓ MCP service tokens stored in session');
  }

  /**
   * Get MCP service token by service name
   */
  getMCPToken(serviceName: string): string | null {
    return this.serviceTokens?.mcp_credentials[serviceName]?.token || null;
  }

  /**
   * Get all service tokens
   */
  getServiceTokens(): ServiceTokens | null {
    return this.serviceTokens;
  }

  /**
   * Check if MCP service token is available
   * Returns true only if we have a valid MCP token
   */
  hasServiceTokens(): boolean {
    return this.serviceTokens !== null &&
           this.serviceTokens.mcp_credentials?.mcp?.token !== undefined;
  }

  /**
   * Clear service tokens from memory (call on logout)
   */
  clearServiceTokens(): void {
    this.serviceTokens = null;
    console.log('✓ MCP service tokens cleared from session');
  }
}

// Export singleton instance
export const sessionService = new SessionService();

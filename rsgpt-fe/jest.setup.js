import '@testing-library/jest-dom'

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter() {
    return {
      push: jest.fn(),
      replace: jest.fn(),
      pathname: '/',
      query: {},
      asPath: '/',
    }
  },
  useSearchParams() {
    return new URLSearchParams()
  },
  usePathname() {
    return '/'
  }
}))

// Mock environment variables with correct Auth0 variable names
process.env.AUTH0_SECRET = 'test-secret-key-that-is-long-enough-for-auth0'
process.env.AUTH0_DOMAIN = 'test.auth0.com'
process.env.AUTH0_CLIENT_ID = 'test-client-id'
process.env.AUTH0_CLIENT_SECRET = 'test-client-secret'
process.env.APP_BASE_URL = 'http://localhost:3000'
process.env.API_BASE_URL = 'http://localhost:8000' 
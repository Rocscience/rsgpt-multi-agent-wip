# GitHub Actions Workflows

This repository uses separate workflows for different environments.

## Workflows

### 1. `build-qa.yml` - QA Environment
- **Triggers on**:
  - Push to `qa` branch
  - Pull requests to `qa` branch
  - Manual trigger via GitHub UI
- **Environment**: `qa`
- **Artifact retention**: 30 days
- **Artifact name**: `rsinsight-desktop-qa-{os}`

### 2. `build.yml` - Production Environment
- **Triggers on**:
  - Push to `main` branch
  - Pull requests to `main` branch
  - Manual trigger via GitHub UI
- **Environment**: `production`
- **Artifact retention**: 90 days
- **Artifact name**: `rsinsight-desktop-prod-{os}`

## Environment Setup

### QA Environment (Already Configured)
✅ Environment `qa` is configured with secrets

### Production Environment (To Be Created)
⏳ Create a `production` environment with the following secrets:

| Secret Name | Description |
|-------------|-------------|
| `AUTH0_DOMAIN` | Auth0 domain for production |
| `AUTH0_CLIENT_ID` | Auth0 client ID for production |
| `AUTH0_AUDIENCE` | Auth0 API audience for production |
| `API_BASE_URL` | Production API base URL |
| `API_AI_BASE_URL` | Production AI core API URL |
| `PINECONE_NAMESPACE` | Pinecone namespace for production |
| `PINECONE_INDEX` | Pinecone index for production |
| `PINECONE_TOP_K` | Pinecone top K results |

> **Note:** Service tokens (`MCP_SERVICE_TOKEN`, `MCP_RSPILE_SERVICE_TOKEN`, `DESKTOP_SERVICE_TOKEN`) are no longer needed in GitHub secrets. They are now fetched from the backend after Auth0 login. Specifically, RSPILE is deprecated, it uses MCP_SERVICE_TOKEN  (one token for all mcp servers) and DESKTOP_SERVICE_TOKE is redundant - since using JWT auth0 as the token for comms between desktop and be

## How to Create Production Environment

1. Go to: `https://github.com/Rocscience/rsgpt-desktop/settings/environments`
2. Click **"New environment"**
3. Name it: `production`
4. Add all 8 secrets listed above with **production** values
5. (Optional) Add protection rules:
   - Required reviewers before deployment
   - Wait timer before deployment
   - Restrict to specific branches (e.g., only `main`)

## Build Process

Both workflows:
1. Use Node.js 22.x (matches local development)
2. Run `npm ci` for clean dependency installation
3. Run `npm run build:prod` for production build
4. Run `npm run package` to create installers
5. Upload artifacts (.exe, .dmg, .AppImage)

## Manual Triggering

Both workflows support manual triggering:
1. Go to **Actions** tab
2. Select the workflow (Build QA or Build Production)
3. Click **"Run workflow"**
4. Select the branch and click **"Run workflow"**

## Artifact Downloads

After a successful build:
1. Go to the workflow run in the **Actions** tab
2. Scroll to **Artifacts** section at the bottom
3. Download the installer for your platform:
   - Windows: `.exe` file
   - macOS: `.dmg` file
   - Linux: `.AppImage` file

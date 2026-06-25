# RSinsight Desktop
## Prerequisites

- Node.js (v18 or higher)
- npm or yarn

## Getting Started

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

This will compile the TypeScript and start the Electron app.

### Building

Build the TypeScript:
```bash
npm run build
```

Package the app for your platform:
```bash
npm run package        # Auto-detect platform
npm run package:mac    # macOS
npm run package:win    # Windows
npm run package:linux  # Linux
```

Built apps will be in the `release/` directory.

## License

TBD

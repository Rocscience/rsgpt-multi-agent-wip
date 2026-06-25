# Contributing to RSinsight Desktop
## Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd rsgpt-desktop
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start development**
   ```bash
   npm run dev
   ```

## Development Workflow

1. **Create a branch**
   `Copy from Linear`

2. **Make your changes**
   - Keep changes small, focused and minimal
   - Follow existing code style
   - Test thoroughly on your platform

3. **Build and test**
   ```bash
   npm run build
   npm start
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add feature description (RSI-XX)"
   ```
   - Make sure to follow the commit guidelines found below

5. **Push and create PR**
   ```bash
   git push origin feature/RSI-XX-feature-name
   ```
   - Use the PR template when creating your pull request
   - Reference the Linear issue number (RSI-XX)

## Code Style

- Use TypeScript for all new code
- Follow existing patterns and conventions
- Keep functions small and focused
- Add comments for complex logic
- Use meaningful variable names

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

## Commit Types

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(export): add AGS file export endpoint` |
| `fix` | Bug fix | `fix(import): handle malformed AGS headers` |
| `docs` | Documentation | `docs(readme): update setup instructions` |
| `style` | Code style changes | `style(format): apply dotnet format` |
| `refactor` | Code refactoring | `refactor(services): simplify export logic` |
| `test` | Test changes | `test(integration): add project controller tests` |
| `build` | Build system changes | `build(deps): update Entity Framework` |
| `ci` | CI configuration | `ci(husky): add pre-commit formatting` |
| `chore` | Maintenance tasks | `chore: update copyright year` |


## Testing

- Test on your target platform (macOS, or Windows)
- Verify tray functionality works correctly
- Ensure app builds without errors
- Check for console errors

## Questions?

Feel free to ask questions in the Linear issue or PR comments.

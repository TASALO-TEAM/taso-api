# Contributing to TASALO API

Thank you for your interest in contributing to TASALO API! This document provides guidelines and instructions for contributing to this project.

**Note:** TASALO API is part of the larger TASALO ecosystem. See the [main repository](https://github.com/TASALO-TEAM/tasalo) for the full project structure.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Features](#suggesting-features)
  - [Submitting Pull Requests](#submitting-pull-requests)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Release Process](#release-process)

---

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/0/code_of_conduct/). By participating, you are expected to uphold this code.

**Key principles:**
- Be respectful and inclusive
- Focus on constructive feedback
- Welcome newcomers and help them learn

---

## Getting Started

**Important:** TASALO API is part of a monorepo structure. The main repository is at `/home/ersus/tasalo/` containing:
- `taso-api/` — Backend FastAPI (this component)
- `taso-bot/` — Telegram Bot
- `taso-app/` — Telegram Mini App
- `taso-ext/` — Browser Extension

1. **Fork the repository** on GitHub (from the main TASALO repo)
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/tasalo.git
   cd tasalo/taso-api
   ```
3. **Add the upstream remote**:
   ```bash
   git remote add upstream https://github.com/TASALO-TEAM/tasalo.git
   ```
4. **Set up your development environment** (see [Development Setup](#development-setup))

---

## How to Contribute

### Reporting Bugs

**Before submitting a bug report:**
- Check if the issue has already been reported in [GitHub Issues](https://github.com/TASALO-TEAM/tasalo/issues)
- Verify the bug exists in the latest version
- Check which component is affected (taso-api, taso-bot, taso-app, etc.)

**How to file a bug report:**

Use the GitHub Issue template and include:

1. **Title**: Clear and descriptive with component prefix (e.g., "[taso-api] ElToque scraper fails with 403 error")
2. **Description**:
   - What you expected to happen
   - What actually happened
   - Steps to reproduce
3. **Environment**:
   - Python version (`python --version`)
   - OS and version
   - TASALO version and component
4. **Logs**: Relevant error messages (use code blocks)
5. **Additional context**: Screenshots, related issues, etc.

---

### Suggesting Features

**Before suggesting a feature:**
- Check existing [feature requests](https://github.com/TASALO-TEAM/tasalo/issues?q=is%3Aissue+label%3Aenhancement)
- Ensure it aligns with project scope (exchange rates for Cuba)
- Consider which component it affects (taso-api, taso-bot, taso-app)

**How to submit a feature request:**

1. **Title**: Start with "[Feature Request]" and component (e.g., "[taso-api] Add support for XYZ source")
2. **Problem statement**: What problem does this solve?
3. **Proposed solution**: How should it work?
4. **Use cases**: Who will benefit from this?
5. **Alternatives considered**: Other ways to solve this

---

### Submitting Pull Requests

**PR Process:**

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/taso-api-your-feature-name
   # or
   git checkout -b fix/taso-api-issue-number-description
   ```
   **Note:** Use component prefix in branch names (taso-api-, taso-bot-, etc.)

2. **Make your changes** following [Coding Standards](#coding-standards)

3. **Write/update tests** for new functionality

4. **Ensure all tests pass**:
   ```bash
   pytest -v --cov=src
   ```

5. **Update documentation** (README, docstrings, etc.)

6. **Commit with clear messages** (see [Commit Guidelines](#commit-guidelines))

7. **Push to your fork**:
   ```bash
   git push origin feature/taso-api-your-feature-name
   ```

8. **Open a Pull Request** on GitHub (to the TASALO main repo)

**PR Checklist:**
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Changelog updated (if applicable)
- [ ] No linting errors
- [ ] All CI checks passing
- [ ] Component prefix in branch name

**PR Review Process:**
1. Maintainer reviews code within 48-72 hours
2. Address any feedback/comments
3. Once approved, PR will be merged
4. Issue will be closed automatically

---

## Development Setup

### Prerequisites

- **Python:** 3.13 or higher
- **uv:** Recommended package manager
- **PostgreSQL:** 14+ (for production testing)
- **Git:** Latest version

### Installation

1. **Clone the TASALO repository:**
   ```bash
   git clone https://github.com/TASALO-TEAM/tasalo.git
   cd tasalo/taso-api
   ```

2. **Create virtual environment with uv:**
   ```bash
   uv venv
   source .venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies:**
   ```bash
   uv pip install -r requirements.txt
   uv pip install pytest pytest-asyncio pytest-cov  # Testing
   uv pip install ruff black mypy  # Linting
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   ```

5. **Initialize database:**
   ```bash
   alembic upgrade head
   ```

6. **Verify setup:**
   ```bash
   pytest  # All tests should pass
   ```

---

## Coding Standards

### Python Style Guide

- **Style:** PEP 8
- **Formatter:** Black (line length: 88)
- **Linter:** Ruff
- **Type hints:** Required for all public functions

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Variables | snake_case | `exchange_rate` |
| Functions | snake_case | `fetch_rates()` |
| Classes | PascalCase | `RateSnapshot` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_TIMEOUT` |
| Private | Leading underscore | `_internal_method()` |

### Commit Guidelines

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(scrapers): add Binance USD/BTC rate support
fix(api): handle null values in ElToque response
docs(readme): update installation instructions
```

---

## Testing

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest -v --cov=src --cov-report=term-missing

# Specific module
pytest tests/test_scrapers/ -v
```

### Writing Tests

- All new features must have tests
- Minimum 80% code coverage
- Async tests use `@pytest.mark.asyncio`
- Mock external API calls

---

## Documentation

### Code Documentation

- **Docstrings:** Required for all public functions/classes
- **Format:** Google style
- **Type hints:** Required for parameters and return values

### User Documentation

- **README.md:** Update for significant changes
- **CHANGELOG.md:** Follow [Keep a Changelog](https://keepachangelog.com/)
- **API docs:** Update OpenAPI spec if endpoints change

---

## Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md` with release notes
3. Create release commit
4. Tag the release
5. Publish to GitHub Releases

---

## Questions?

- **General questions:** Open a [Discussion](https://github.com/TASALO-TEAM/tasalo/discussions)
- **Bug reports:** Open an [Issue](https://github.com/TASALO-TEAM/tasalo/issues) (include component prefix)
- **Security issues:** Email security@tasalo.app (do not open public issue)

---

## TASALO Ecosystem

TASALO consists of multiple components:

| Component | Description | Stack |
|-----------|-------------|-------|
| **taso-api** | Backend FastAPI | FastAPI, PostgreSQL, SQLAlchemy |
| **taso-bot** | Telegram Bot | python-telegram-bot |
| **taso-app** | Telegram Mini App | Flask, Tailwind CSS |
| **taso-ext** | Browser Extension | Vanilla JS (Manifest V3) |

Each component has its own CONTRIBUTING.md with specific guidelines.

---

Thank you for contributing to TASALO API! 🎉

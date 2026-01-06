# WDS Component Adoption Metrics

Track and analyze how `@transferwise/components` is adopted.

## Quick Start

### 1. First Time Setup

```bash
pnpm run init
```

**⚠️ Important**: Provide a **dedicated folder** for the tool to manage repositories (not your working code directory because we need to grab latest on updates).

### 2. Weekly Updates

```bash
pnpm run update
```

This will:
- Pull latest changes from all repositories
- Analyze adoption patterns
- Update dashboard

### 3. View Dashboard

```bash
pnpm run dev
```

Opens the interactive dashboard at http://localhost:3000/site/. Double check before pushing changes.

## Configuration

### Add/Remove Repositories

Edit `config/repo_config.py`:

```python
REPO_NAMES = [
    'account-page',
    'balance-flows-web',
    'your-repo-name',
    # ... add your repos
]
```

### Files

**Config:**
- `config/config.json` - local code base path (gitignored)
- `config/repo_config.py` - list of repositories to analyze

**Scripts:**
- `scripts/init.py` - first-time setup wizard
- `scripts/update.py` - weekly automation script
- `scripts/get_neptune_web_releases.py` - extract neptune-web releases
- `scripts/analyze_adoption_patterns.py` - generate dashboard

**Data:**
- `data/component_releases.json` - neptune-web releases over time

**Github Pages Site:**
- `site/adoption_data.json` - dashboard data
- `site/index.html` - interactive dashboard

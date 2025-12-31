# Version Tracking Tools for @transferwise/components

## Overview
These scripts help you track how `@transferwise/components` (or any npm package) is adopted across your company's repositories.

## Scripts

### 1. `track_component_versions.py` - Single Repository History
Analyzes git history of a single repository to track version changes over time.

```bash
# Basic usage - analyze current repo for last 12 months
python3 track_component_versions.py

# Analyze specific repo for last 6 months
python3 track_component_versions.py --repo /path/to/repo --months 6

# Save to specific JSON file
python3 track_component_versions.py --output my_analysis.json

# Track a different package
python3 track_component_versions.py --package "@wise/art"
```

### 2. `track_versions_multi_repo.py` - Multiple Repository Analysis
Analyzes version history across multiple repositories to understand adoption patterns.

```bash
# Option 1: Scan all repos in parent directory
python3 track_versions_multi_repo.py --repos ../

# Option 2: Specify repos directly
python3 track_versions_multi_repo.py --repos ~/Code/repo1,~/Code/repo2,~/Code/repo3

# Export to CSV for Excel analysis
python3 track_versions_multi_repo.py --repos ../ --csv

# Export to JSON for programmatic access
python3 track_versions_multi_repo.py --repos ../ --json

# Analyze last 6 months only
python3 track_versions_multi_repo.py --repos ../ --months 6
```

### 3. `analyze_adoption_patterns.py` - Adoption Dashboard (Current Tool)
Generates interactive HTML dashboard comparing release dates with adoption dates across multiple repositories.

```bash
# Generate dashboard for last 36 months
python3 analyze_adoption_patterns.py --releases component_releases_20251218_130049.json --months 36

# Generate dashboard for last 12 months
python3 analyze_adoption_patterns.py --releases component_releases_20251218_130049.json --months 12
```

**Note**: Repository list is configured in the `REPO_NAMES` constant at the top of the script. Edit this list to add/remove repositories.

## Output Files

### Single Repository Analysis
- **Console Report**: Detailed version history with dates and adoption timeline
- **JSON File**: `component_versions_TIMESTAMP.json` - Complete change history

### Multi-Repository Analysis  
- **Console Report**: Aggregated insights including:
  - Current version distribution across repos
  - Version introduction timeline
  - Adoption speed metrics
  - Repositories behind latest version
- **CSV File**: `version_history_multi_TIMESTAMP.csv` - All version changes for Excel
- **JSON File**: `version_analysis_multi_TIMESTAMP.json` - Complete analysis data

## Transitive Dependency Overrides

The scripts now support pnpm's transitive dependency overrides format:
```json
{
  "pnpm": {
    "overrides": {
      "@wise/account-consent>@transferwise/components": "^46.115.1"
    }
  }
}
```

This allows you to track versions even when they're specified as overrides for dependencies of dependencies. The reports will show:
- `(direct)` - Regular dependency
- `(override)` - Direct pnpm override
- `(via parent-package)` - Transitive override through another package

## Key Insights You Can Get

### From Single Repository:
- Every version change with commit details
- How long each version was used
- Average time between updates
- Who made each update

### From Multiple Repositories:
- Which repos adopt new versions first (early adopters)
- Which repos are behind (laggards)
- How quickly versions spread across the organization
- Version fragmentation (how many different versions are in use)

## Best Practices

1. **Generate Adoption Dashboard**: Run the adoption analysis to get interactive visualizations
   ```bash
   python3 analyze_adoption_patterns.py --releases component_releases_20251218_130049.json --months 36
   ```

2. **Weekly Monitoring**: Run the multi-repo script weekly to track adoption progress
   ```bash
   python3 track_versions_multi_repo.py --repos ../ --csv
   ```

3. **Historical Analysis**: Use single-repo script for deep dives
   ```bash
   python3 track_component_versions.py --repo /path/to/early-adopter-repo
   ```

4. **Track Multiple Packages**: Monitor different packages by changing the `--package` flag
   ```bash
   python3 track_versions_multi_repo.py --repos ../ --package "@wise/art"
   ```

## Performance Notes

- The multi-repo script processes repositories in parallel (up to 4 at a time)
- For large histories, the initial run may take a few minutes
- Use `--no-parallel` flag if you encounter issues with parallel processing

## Example Workflow

1. **Initial Setup**: Configure repositories in `analyze_adoption_patterns.py`
   ```python
   # Edit REPO_NAMES constant at top of file
   REPO_NAMES = [
       'account-page',
       'balance-flows-web',
       'your-repo-name',
       # ... add all your repos
   ]
   ```

2. **Extract Release Data**: Get release dates from neptune-web (one-time or when updating)
   ```bash
   python3 extract_component_releases.py --repo /path/to/neptune-web --months 36
   ```

3. **Generate Dashboard**: Create interactive adoption analysis
   ```bash
   python3 analyze_adoption_patterns.py --releases component_releases_*.json --months 36
   ```

4. **View Results**: Open the generated `adoption_dashboard_*.html` file in your browser to see:
   - Interactive timeline chart with clickable markers
   - Repository filters to focus on specific repos
   - Detailed comparison table with aggregated metrics
   - CSV exports for further analysis

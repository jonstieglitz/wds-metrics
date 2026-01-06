#!/usr/bin/env python3
"""
Weekly update script for wds-metrics.
Pulls latest changes from all repositories and regenerates analysis data.
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import config module
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import get_code_base_path
from config.repo_config import REPO_NAMES


def git_pull_repo(repo_path: Path) -> tuple[bool, str]:
    """Pull latest changes from a repository."""
    try:
        # Check if there are uncommitted changes
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            check=True
        )
        
        if status_result.stdout.strip():
            return False, "Uncommitted changes detected, skipping"
        
        # Get the default branch (usually main or master)
        default_branch_result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            check=True
        )
        default_branch = default_branch_result.stdout.strip().replace("refs/remotes/origin/", "")
        
        # Checkout the default branch
        subprocess.run(
            ["git", "checkout", default_branch],
            capture_output=True,
            text=True,
            cwd=repo_path,
            check=True
        )
        
        # Pull latest changes
        result = subprocess.run(
            ["git", "pull"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            check=True
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()


def update_all_repos(code_base_path: Path) -> dict:
    """Update all repositories by pulling latest changes."""
    print("=" * 60)
    print("Updating repositories...")
    print("=" * 60)
    print()
    
    results = {
        'success': [],
        'failed': [],
        'skipped': []
    }
    
    for repo_name in REPO_NAMES:
        repo_path = code_base_path / repo_name
        
        if not repo_path.exists():
            print(f"  ⚠️  {repo_name} - not found, skipping")
            results['skipped'].append(repo_name)
            continue
        
        if not (repo_path / '.git').exists():
            print(f"  ⚠️  {repo_name} - not a git repository, skipping")
            results['skipped'].append(repo_name)
            continue
        
        print(f"  📥 {repo_name} - pulling latest...")
        success, output = git_pull_repo(repo_path)
        
        if success:
            if "Already up to date" in output or "Already up-to-date" in output:
                print(f"  ✓ {repo_name} - already up to date")
            else:
                print(f"  ✅ {repo_name} - updated")
            results['success'].append(repo_name)
        else:
            print(f"  ❌ {repo_name} - failed: {output}")
            results['failed'].append(repo_name)
    
    return results


def run_extract_releases(code_base_path: Path) -> bool:
    """Run get_neptune_web_releases.py to get latest release data."""
    print()
    print("=" * 60)
    print("Extracting component releases...")
    print("=" * 60)
    print()
    
    neptune_path = code_base_path / "neptune-web"
    
    if not neptune_path.exists():
        print("❌ neptune-web repository not found, skipping release extraction")
        return False
    
    try:
        result = subprocess.run(
            ["python3", "scripts/get_neptune_web_releases.py", "--json"],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to extract releases: {e.stderr}")
        return False


def run_adoption_analysis() -> bool:
    """Run analyze_adoption_patterns.py to regenerate analysis."""
    print()
    print("=" * 60)
    print("Analyzing adoption patterns...")
    print("=" * 60)
    print()
    
    # Check if component_releases.json exists
    releases_file = Path("data/component_releases.json")
    
    if not releases_file.exists():
        print("❌ No component releases file found. Run get_neptune_web_releases.py first.")
        return False
    
    try:
        result = subprocess.run(
            ["python3", "scripts/analyze_adoption_patterns.py"],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to analyze adoption patterns: {e.stderr}")
        return False


def main():
    """Run the weekly update process."""
    print("=" * 60)
    print("WDS Metrics - Weekly Update")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    try:
        code_base_path = get_code_base_path()
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ Configuration error: {e}")
        print("Please run 'pnpm run init' first to set up your configuration.")
        return 1
    
    print(f"Code base path: {code_base_path}")
    print()
    
    # Step 1: Update all repositories
    update_results = update_all_repos(code_base_path)
    
    print()
    print("-" * 60)
    print(f"Repository update summary:")
    print(f"  ✅ Success: {len(update_results['success'])}")
    print(f"  ❌ Failed: {len(update_results['failed'])}")
    print(f"  ⚠️  Skipped: {len(update_results['skipped'])}")
    print("-" * 60)
    
    if update_results['failed']:
        print()
        print("⚠️  Some repositories failed to update. Continuing anyway...")
    
    # Step 2: Extract latest component releases
    extract_success = run_extract_releases(code_base_path)
    
    if not extract_success:
        print()
        print("⚠️  Failed to extract component releases. Skipping adoption analysis.")
        return 1
    
    # Step 3: Analyze adoption patterns
    analysis_success = run_adoption_analysis()
    
    if not analysis_success:
        print()
        print("⚠️  Failed to analyze adoption patterns.")
        return 1
    
    # Summary
    print()
    print("=" * 60)
    print("✅ Weekly update complete!")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    print("Generated files:")
    print("  - data/component_releases.json (release data)")
    print("  - site/adoption_data.json (dashboard data)")
    print("  - site/index.html (interactive dashboard)")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

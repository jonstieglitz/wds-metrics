#!/usr/bin/env python3
"""
Initialization script for wds-metrics.
Prompts the user for the code base path and saves it to configuration.
Clones missing repositories from GitHub.
"""

import sys
import subprocess
from pathlib import Path

# Add parent directory to path so we can import config module
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import set_code_base_path
from config.repo_config import REPO_NAMES, GITHUB_SSH_BASE


def clone_repository(repo_name: str, target_dir: Path) -> bool:
    """Clone a repository if it doesn't exist."""
    repo_path = target_dir / repo_name
    
    if repo_path.exists():
        if (repo_path / '.git').exists():
            print(f"  ✓ {repo_name} already exists")
            return True
        else:
            print(f"  ⚠️  {repo_name} directory exists but is not a git repository")
            return False
    
    # Clone the repository
    git_url = f"{GITHUB_SSH_BASE}/{repo_name}.git"
    print(f"  📥 Cloning {repo_name}...")
    
    try:
        result = subprocess.run(
            ["git", "clone", git_url, str(repo_path)],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"  ✅ Successfully cloned {repo_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Failed to clone {repo_name}: {e.stderr.strip()}")
        return False


def clone_missing_repositories(code_base_path: Path) -> None:
    """Clone all missing repositories."""
    print()
    print("=" * 60)
    print("Checking and cloning repositories...")
    print("=" * 60)
    print()
    
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    for repo_name in REPO_NAMES:
        repo_path = code_base_path / repo_name
        
        if repo_path.exists() and (repo_path / '.git').exists():
            print(f"  ✓ {repo_name} already exists")
            skipped_count += 1
        else:
            if clone_repository(repo_name, code_base_path):
                success_count += 1
            else:
                failed_count += 1
    
    print()
    print("-" * 60)
    print(f"Summary: {skipped_count} existing, {success_count} cloned, {failed_count} failed")
    print("-" * 60)


def main():
    """Run the initialization process."""
    print("=" * 60)
    print("WDS Metrics - Configuration Setup")
    print("=" * 60)
    print()
    print("This script will configure the path to your code base directory.")
    print("This is the parent directory containing all your repositories.")
    print()
    
    # Prompt for the code base path
    while True:
        path_input = input("Enter the path to your code base directory: ").strip()
        
        if not path_input:
            print("❌ Path cannot be empty. Please try again.")
            continue
        
        try:
            # Expand and resolve the path
            path = Path(path_input).expanduser().resolve()
            
            # Validate the path
            if not path.exists():
                print(f"❌ Path does not exist: {path}")
                retry = input("Would you like to try again? (y/n): ").strip().lower()
                if retry != 'y':
                    print("Configuration cancelled.")
                    return 1
                continue
            
            if not path.is_dir():
                print(f"❌ Path is not a directory: {path}")
                retry = input("Would you like to try again? (y/n): ").strip().lower()
                if retry != 'y':
                    print("Configuration cancelled.")
                    return 1
                continue
            
            # Save the configuration
            set_code_base_path(str(path))
            
            # Clone missing repositories
            clone_prompt = input("\nWould you like to clone missing repositories now? (y/n): ").strip().lower()
            if clone_prompt == 'y':
                clone_missing_repositories(path)
            
            print()
            print("=" * 60)
            print("✅ Setup complete!")
            print("=" * 60)
            print()
            print("You can now run:")
            print("  pnpm run update  # Weekly updates")
            print("  pnpm run dev     # View dashboard")
            print()
            return 0
                
        except Exception as e:
            print(f"❌ Error: {e}")
            retry = input("Would you like to try again? (y/n): ").strip().lower()
            if retry != 'y':
                print("Configuration cancelled.")
                return 1


if __name__ == "__main__":
    sys.exit(main())

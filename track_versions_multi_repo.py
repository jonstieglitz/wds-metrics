#!/usr/bin/env python3
"""
Track the version history of @transferwise/components across multiple repositories.
Analyzes git history to understand version adoption patterns across your company.
"""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sys
import argparse
from pathlib import Path
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import os


class MultiRepoVersionTracker:
    """Track version changes across multiple repositories."""
    
    def __init__(self, package_name: str = "@transferwise/components"):
        self.package_name = package_name
        self.all_changes = []
        self.repo_results = {}
        
    def get_repo_list(self, repos_input: str) -> List[Path]:
        """Get list of repositories from file or directory scan."""
        repos = []
        
        # Check if it's a file with repo list
        if Path(repos_input).is_file():
            with open(repos_input, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        repo_path = Path(line).expanduser().resolve()
                        if repo_path.exists() and (repo_path / '.git').exists():
                            repos.append(repo_path)
                        else:
                            print(f"⚠️  Skipping {line}: Not a valid git repository")
        
        # Check if it's a directory to scan
        elif Path(repos_input).is_dir():
            parent = Path(repos_input).resolve()
            for item in parent.iterdir():
                if item.is_dir() and (item / '.git').exists() and (item / 'package.json').exists():
                    repos.append(item)
        
        # Treat as comma-separated list of paths
        else:
            for repo_path_str in repos_input.split(','):
                repo_path = Path(repo_path_str.strip()).expanduser().resolve()
                if repo_path.exists() and (repo_path / '.git').exists():
                    repos.append(repo_path)
                else:
                    print(f"⚠️  Skipping {repo_path_str}: Not a valid git repository")
        
        return sorted(set(repos))
    
    def get_package_json_at_commit(self, repo_path: Path, commit_hash: str) -> Optional[Dict]:
        """Get the contents of package.json at a specific commit."""
        try:
            result = subprocess.run(
                ["git", "show", f"{commit_hash}:package.json"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                check=True
            )
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None
    
    def extract_component_versions(self, package_json: Dict) -> Dict[str, Optional[str]]:
        """Extract package versions from package.json."""
        versions = {
            "dependency": None,
            "override": None,
            "transitive_overrides": []
        }
        
        # Check dependencies
        if "dependencies" in package_json:
            versions["dependency"] = package_json["dependencies"].get(self.package_name)
        
        # Check devDependencies
        if not versions["dependency"] and "devDependencies" in package_json:
            versions["dependency"] = package_json["devDependencies"].get(self.package_name)
        
        # Check pnpm overrides
        if "pnpm" in package_json and "overrides" in package_json["pnpm"]:
            overrides = package_json["pnpm"]["overrides"]
            
            # Direct override
            versions["override"] = overrides.get(self.package_name)
            
            # Transitive overrides (format: "parent-package>@transferwise/components": "version")
            for key, value in overrides.items():
                if ">" in key and key.endswith(f">{self.package_name}"):
                    parent_package = key.split(">")[0]
                    versions["transitive_overrides"].append({
                        "parent": parent_package,
                        "version": value
                    })
        
        return versions
    
    def get_commit_info(self, repo_path: Path, commit_hash: str) -> Dict:
        """Get commit metadata."""
        format_string = "%H%n%ai%n%an%n%ae%n%s"
        result = subprocess.run(
            ["git", "show", "-s", f"--format={format_string}", commit_hash],
            capture_output=True,
            text=True,
            cwd=repo_path,
            check=True
        )
        
        lines = result.stdout.strip().split("\n")
        return {
            "hash": lines[0],
            "date": lines[1],
            "author_name": lines[2],
            "author_email": lines[3],
            "message": lines[4] if len(lines) > 4 else ""
        }
    
    def track_repo_version_changes(self, repo_path: Path, since_date: datetime, until_date: datetime) -> Dict:
        """Track version changes for a single repository."""
        repo_name = repo_path.name
        print(f"  Processing {repo_name}...")
        
        # Build git log command
        cmd = ["git", "log", "--format=%H", "--reverse"]
        cmd.append(f"--since={since_date.isoformat()}")
        cmd.append(f"--until={until_date.isoformat()}")
        cmd.append("--")
        cmd.append("package.json")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=repo_path,
                check=True
            )
            
            commits = result.stdout.strip().split("\n")
            commits = [c for c in commits if c]
            
            changes = []
            last_versions = {"dependency": None, "override": None, "transitive_overrides": []}
            
            for commit_hash in commits:
                package_json = self.get_package_json_at_commit(repo_path, commit_hash)
                if not package_json:
                    continue
                
                versions = self.extract_component_versions(package_json)
                
                # Determine effective version (priority: direct override > transitive override > dependency)
                effective_version = versions["override"]
                if not effective_version and versions["transitive_overrides"]:
                    # Use the first transitive override if available
                    effective_version = versions["transitive_overrides"][0]["version"]
                if not effective_version:
                    effective_version = versions["dependency"]
                
                last_effective = last_versions["override"]
                if not last_effective and last_versions["transitive_overrides"]:
                    last_effective = last_versions["transitive_overrides"][0]["version"]
                if not last_effective:
                    last_effective = last_versions["dependency"]
                
                # Check if any version changed
                changed = False
                if versions["dependency"] != last_versions["dependency"] or \
                   versions["override"] != last_versions["override"] or \
                   versions["transitive_overrides"] != last_versions["transitive_overrides"]:
                    changed = True
                
                if changed and (effective_version != last_effective):
                    commit_info = self.get_commit_info(repo_path, commit_hash)
                    
                    change_record = {
                        "repository": repo_name,
                        "commit": commit_info["hash"][:8],
                        "date": commit_info["date"],
                        "author": commit_info["author_name"],
                        "message": commit_info["message"][:80],
                        "dependency_version": versions["dependency"],
                        "override_version": versions["override"],
                        "transitive_overrides": versions["transitive_overrides"],
                        "effective_version": effective_version,
                        "previous_effective": last_effective
                    }
                    changes.append(change_record)
                
                last_versions = versions.copy()
            
            # Get current version
            current_package_json = repo_path / "package.json"
            current_version = None
            current_version_details = {}
            if current_package_json.exists():
                with open(current_package_json, 'r') as f:
                    data = json.load(f)
                    versions = self.extract_component_versions(data)
                    current_version = versions["override"]
                    if not current_version and versions["transitive_overrides"]:
                        current_version = versions["transitive_overrides"][0]["version"]
                    if not current_version:
                        current_version = versions["dependency"]
                    current_version_details = versions
            
            return {
                "repository": repo_name,
                "path": str(repo_path),
                "changes": changes,
                "total_changes": len(changes),
                "current_version": current_version,
                "current_version_details": current_version_details,
                "commits_analyzed": len(commits)
            }
            
        except subprocess.CalledProcessError as e:
            print(f"    ❌ Error processing {repo_name}: {e}")
            return {
                "repository": repo_name,
                "path": str(repo_path),
                "error": str(e),
                "changes": [],
                "total_changes": 0
            }
    
    def parse_git_date(self, date_str: str) -> datetime:
        """Parse a git date string to datetime object."""
        parts = date_str.split()
        if len(parts) >= 2:
            date_time = f"{parts[0]} {parts[1]}"
            return datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")
        return datetime.now()
    
    def parse_version(self, version_str: str) -> tuple:
        """Parse a semantic version string for comparison."""
        if not version_str:
            return (0, 0, 0)
        # Remove ^ or ~ prefix
        version = version_str.lstrip('^~')
        parts = version.split('.')
        try:
            return tuple(int(p) for p in parts[:3])
        except (ValueError, IndexError):
            return (0, 0, 0)
    
    def analyze_adoption_patterns(self) -> Dict:
        """Analyze version adoption patterns across all repositories."""
        patterns = {
            "version_timeline": {},
            "adoption_speed": {},
            "version_distribution": {},
            "laggards": [],
            "early_adopters": []
        }
        
        # Collect all unique versions and their first/last appearance
        version_dates = {}
        current_versions = {}
        
        for repo_result in self.repo_results.values():
            if "error" in repo_result:
                continue
            
            # Track current version
            if repo_result.get("current_version"):
                current_versions[repo_result["repository"]] = repo_result["current_version"]
            
            for change in repo_result["changes"]:
                version = change["effective_version"]
                if not version:
                    continue
                
                date = self.parse_git_date(change["date"])
                
                if version not in version_dates:
                    version_dates[version] = {
                        "first_seen": date,
                        "last_seen": date,
                        "first_repo": change["repository"],
                        "repos": set()
                    }
                else:
                    if date < version_dates[version]["first_seen"]:
                        version_dates[version]["first_seen"] = date
                        version_dates[version]["first_repo"] = change["repository"]
                    if date > version_dates[version]["last_seen"]:
                        version_dates[version]["last_seen"] = date
                
                version_dates[version]["repos"].add(change["repository"])
        
        # Build timeline
        patterns["version_timeline"] = {
            version: {
                "first_seen": info["first_seen"].isoformat(),
                "first_repo": info["first_repo"],
                "total_repos": len(info["repos"]),
                "repos": list(info["repos"])
            }
            for version, info in sorted(version_dates.items(), 
                                       key=lambda x: x[1]["first_seen"])
        }
        
        # Current version distribution
        version_counts = {}
        for version in current_versions.values():
            version_counts[version] = version_counts.get(version, 0) + 1
        
        patterns["version_distribution"] = version_counts
        
        # Find latest version
        if version_counts:
            latest_version = max(version_counts.keys(), key=self.parse_version)
            
            # Identify laggards (repos not on latest)
            for repo, version in current_versions.items():
                if version != latest_version:
                    patterns["laggards"].append({
                        "repository": repo,
                        "current_version": version,
                        "latest_version": latest_version
                    })
        
        # Calculate adoption speed (days from first appearance to reaching X repos)
        for version, info in version_dates.items():
            if len(info["repos"]) > 1:
                days_to_full = (info["last_seen"] - info["first_seen"]).days
                patterns["adoption_speed"][version] = {
                    "days_to_adoption": days_to_full,
                    "repos_adopted": len(info["repos"])
                }
        
        return patterns
    
    def generate_aggregated_report(self, patterns: Dict, since_date: datetime, until_date: datetime) -> str:
        """Generate a comprehensive report across all repositories."""
        report = []
        
        # Header
        report.append("=" * 100)
        report.append(f"Multi-Repository Version History Analysis")
        report.append(f"Package: {self.package_name}")
        report.append(f"Period: {since_date.strftime('%Y-%m-%d')} to {until_date.strftime('%Y-%m-%d')}")
        report.append("=" * 100)
        
        # Summary
        total_repos = len(self.repo_results)
        repos_with_package = sum(1 for r in self.repo_results.values() 
                                if r.get("current_version"))
        total_changes = sum(r.get("total_changes", 0) for r in self.repo_results.values())
        
        report.append("\n## Summary")
        report.append(f"- Repositories analyzed: {total_repos}")
        report.append(f"- Repositories using {self.package_name}: {repos_with_package}")
        report.append(f"- Total version changes across all repos: {total_changes}")
        report.append(f"- Average changes per repo: {total_changes/repos_with_package:.1f}" if repos_with_package else "")
        
        # Current version distribution
        if patterns["version_distribution"]:
            report.append("\n## Current Version Distribution")
            report.append("-" * 50)
            for version, count in sorted(patterns["version_distribution"].items(), 
                                        key=lambda x: x[1], reverse=True):
                percentage = (count / repos_with_package * 100) if repos_with_package else 0
                bar = "█" * int(percentage / 2)
                report.append(f"{version:20} | {count:3} repos | {percentage:5.1f}% |{bar}")
        
        # Version adoption timeline
        if patterns["version_timeline"]:
            report.append("\n## Version Introduction Timeline")
            report.append("-" * 50)
            for version, info in patterns["version_timeline"].items():
                report.append(f"{version:20} | First: {info['first_seen'][:10]} | {info['first_repo']:20} | Adopted by {info['total_repos']} repos")
        
        # Adoption speed
        if patterns["adoption_speed"]:
            report.append("\n## Adoption Speed Analysis")
            report.append("-" * 50)
            fastest = sorted(patterns["adoption_speed"].items(), 
                           key=lambda x: x[1]["days_to_adoption"])[:5]
            for version, info in fastest:
                report.append(f"{version:20} | {info['days_to_adoption']:3} days to reach {info['repos_adopted']} repos")
        
        # Laggards
        if patterns["laggards"]:
            report.append(f"\n## Repositories Behind Latest Version")
            report.append("-" * 50)
            for lag in sorted(patterns["laggards"], key=lambda x: x["repository"]):
                report.append(f"{lag['repository']:30} | {lag['current_version']:15} | Latest: {lag['latest_version']}")
        
        # Repository details
        report.append("\n## Repository Change Summary")
        report.append("-" * 50)
        for repo_name, result in sorted(self.repo_results.items()):
            if "error" not in result:
                changes = result.get("total_changes", 0)
                current = result.get("current_version", "Not found")
                details = result.get("current_version_details", {})
                
                # Add annotation for how the version is specified
                version_type = ""
                if details.get("override"):
                    version_type = " (override)"
                elif details.get("transitive_overrides"):
                    parents = ", ".join(t["parent"] for t in details["transitive_overrides"][:2])
                    version_type = f" (via {parents})"
                elif details.get("dependency"):
                    version_type = " (direct)"
                
                current_str = current if current else "Not found"
                report.append(f"{repo_name:30} | {changes:3} changes | Current: {current_str:15}{version_type}")
        
        return "\n".join(report)
    
    def export_to_csv(self, filename: str = None):
        """Export all changes to CSV for analysis."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"version_history_multi_{timestamp}.csv"
        
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['repository', 'date', 'commit', 'author', 'message',
                         'previous_version', 'new_version', 'version_type', 'parent_package']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for result in self.repo_results.values():
                for change in result.get("changes", []):
                    version_type = 'direct'
                    parent_package = ''
                    if change.get('override_version'):
                        version_type = 'override'
                    elif change.get('transitive_overrides'):
                        version_type = 'transitive'
                        parent_package = ', '.join(t['parent'] for t in change['transitive_overrides'])
                    
                    writer.writerow({
                        'repository': change['repository'],
                        'date': change['date'],
                        'commit': change['commit'],
                        'author': change['author'],
                        'message': change['message'],
                        'previous_version': change['previous_effective'],
                        'new_version': change['effective_version'],
                        'version_type': version_type,
                        'parent_package': parent_package
                    })
        
        print(f"📊 Exported detailed history to {filename}")
        return filename
    
    def export_to_json(self, filename: str = None):
        """Export all data to JSON."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"version_analysis_multi_{timestamp}.json"
        
        output = {
            "package": self.package_name,
            "generated_at": datetime.now().isoformat(),
            "repository_results": self.repo_results,
            "adoption_patterns": self.analyze_adoption_patterns()
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"💾 Saved complete analysis to {filename}")
        return filename
    
    def process_repositories(self, repos: List[Path], since_date: datetime, 
                           until_date: datetime, parallel: bool = True):
        """Process all repositories."""
        print(f"\n🔍 Analyzing {len(repos)} repositories...")
        print("-" * 50)
        
        if parallel and len(repos) > 1:
            # Process in parallel for speed
            with ThreadPoolExecutor(max_workers=min(4, len(repos))) as executor:
                futures = {
                    executor.submit(self.track_repo_version_changes, repo, since_date, until_date): repo
                    for repo in repos
                }
                
                for future in as_completed(futures):
                    result = future.result()
                    self.repo_results[result["repository"]] = result
        else:
            # Process sequentially
            for repo in repos:
                result = self.track_repo_version_changes(repo, since_date, until_date)
                self.repo_results[result["repository"]] = result


def main():
    parser = argparse.ArgumentParser(
        description="Track @transferwise/components version history across multiple repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze repositories listed in a file
  python track_versions_multi_repo.py --repos repos.txt
  
  # Analyze all repos in parent directory
  python track_versions_multi_repo.py --repos ../
  
  # Analyze specific repos
  python track_versions_multi_repo.py --repos ~/Code/repo1,~/Code/repo2
  
  # Analyze last 6 months with CSV export
  python track_versions_multi_repo.py --repos repos.txt --months 6 --csv
        """
    )
    
    parser.add_argument("--repos", required=True, 
                       help="Repository list: file path, directory to scan, or comma-separated paths")
    parser.add_argument("--months", type=int, default=12, 
                       help="Number of months to look back (default: 12)")
    parser.add_argument("--package", default="@transferwise/components", 
                       help="Package name to track")
    parser.add_argument("--csv", action="store_true", 
                       help="Export results to CSV")
    parser.add_argument("--json", action="store_true", 
                       help="Export results to JSON")
    parser.add_argument("--no-parallel", action="store_true",
                       help="Process repositories sequentially instead of in parallel")
    
    args = parser.parse_args()
    
    # Get repositories
    tracker = MultiRepoVersionTracker(args.package)
    repos = tracker.get_repo_list(args.repos)
    
    if not repos:
        print("❌ No valid repositories found")
        return 1
    
    print(f"Found {len(repos)} repositories to analyze:")
    for repo in repos:
        print(f"  - {repo.name}")
    
    # Calculate date range
    until_date = datetime.now()
    since_date = until_date - timedelta(days=args.months * 30)
    
    # Process repositories
    tracker.process_repositories(repos, since_date, until_date, 
                               parallel=not args.no_parallel)
    
    # Analyze patterns
    patterns = tracker.analyze_adoption_patterns()
    
    # Generate and print report
    report = tracker.generate_aggregated_report(patterns, since_date, until_date)
    print(report)
    
    # Export if requested
    if args.csv:
        tracker.export_to_csv()
    
    if args.json or True:  # Always save JSON for detailed analysis
        tracker.export_to_json()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

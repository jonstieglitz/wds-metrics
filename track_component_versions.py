#!/usr/bin/env python3
"""
Track the version history of @transferwise/components in package.json files.
This script analyzes git history to find every change to the package version.
"""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sys
import argparse
from pathlib import Path


class ComponentVersionTracker:
    """Track version changes of @transferwise/components through git history."""
    
    def __init__(self, repo_path: str = ".", package_name: str = "@transferwise/components"):
        self.repo_path = Path(repo_path).resolve()
        self.package_name = package_name
        self.version_history: List[Dict] = []
        
    def get_package_json_at_commit(self, commit_hash: str) -> Optional[Dict]:
        """Get the contents of package.json at a specific commit."""
        try:
            result = subprocess.run(
                ["git", "show", f"{commit_hash}:package.json"],
                capture_output=True,
                text=True,
                cwd=self.repo_path,
                check=True
            )
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None
    
    def extract_component_versions(self, package_json: Dict) -> Dict[str, Optional[str]]:
        """Extract @transferwise/components versions from package.json."""
        versions = {
            "dependency": None,
            "override": None,
            "transitive_overrides": []
        }
        
        # Check dependencies
        if "dependencies" in package_json:
            versions["dependency"] = package_json["dependencies"].get(self.package_name)
        
        # Check devDependencies (just in case)
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
    
    def get_commit_info(self, commit_hash: str) -> Dict:
        """Get commit metadata."""
        format_string = "%H%n%ai%n%an%n%ae%n%s"
        result = subprocess.run(
            ["git", "show", "-s", f"--format={format_string}", commit_hash],
            capture_output=True,
            text=True,
            cwd=self.repo_path,
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
    
    def track_version_changes(self, since_date: Optional[datetime] = None, until_date: Optional[datetime] = None) -> List[Dict]:
        """Track all version changes in git history within the specified date range."""
        # Build git log command
        cmd = ["git", "log", "--format=%H", "--reverse"]
        
        if since_date:
            cmd.append(f"--since={since_date.isoformat()}")
        if until_date:
            cmd.append(f"--until={until_date.isoformat()}")
        
        # Only look at commits that touched package.json
        cmd.append("--")
        cmd.append("package.json")
        
        # Get all commits that modified package.json
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.repo_path,
            check=True
        )
        
        commits = result.stdout.strip().split("\n")
        commits = [c for c in commits if c]  # Remove empty strings
        
        print(f"Found {len(commits)} commits that modified package.json")
        
        changes = []
        last_versions = {"dependency": None, "override": None, "transitive_overrides": []}
        
        for i, commit_hash in enumerate(commits):
            if (i + 1) % 10 == 0:
                print(f"Processing commit {i + 1}/{len(commits)}...")
            
            package_json = self.get_package_json_at_commit(commit_hash)
            if not package_json:
                continue
            
            versions = self.extract_component_versions(package_json)
            commit_info = self.get_commit_info(commit_hash)
            
            # Determine effective version
            effective_version = versions["override"]
            if not effective_version and versions["transitive_overrides"]:
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
            change_details = []
            
            if versions["dependency"] != last_versions["dependency"]:
                changed = True
                change_details.append(f"dependency: {last_versions['dependency']} → {versions['dependency']}")
            
            if versions["override"] != last_versions["override"]:
                changed = True
                change_details.append(f"override: {last_versions['override']} → {versions['override']}")
            
            if versions["transitive_overrides"] != last_versions["transitive_overrides"]:
                changed = True
                if versions["transitive_overrides"]:
                    trans_info = f"transitive via {versions['transitive_overrides'][0]['parent']}: {versions['transitive_overrides'][0]['version']}"
                    change_details.append(trans_info)
            
            if changed and (effective_version != last_effective):
                
                change_record = {
                    "commit": commit_info["hash"][:8],
                    "date": commit_info["date"],
                    "author": commit_info["author_name"],
                    "message": commit_info["message"][:80],
                    "dependency_version": versions["dependency"],
                    "override_version": versions["override"],
                    "effective_version": effective_version,
                    "previous_effective": last_effective,
                    "changes": ", ".join(change_details)
                }
                changes.append(change_record)
            
            last_versions = versions.copy()
        
        return changes
    
    def parse_git_date(self, date_str: str) -> datetime:
        """Parse a git date string to datetime object."""
        # Git date format: "2024-01-01 12:00:00 +0000" or similar
        # Remove timezone info first
        date_part = date_str.split('+')[0].split('-')[0:3]  # Keep first 3 parts (year-month-day)
        if len(date_part) == 3 and ' ' in date_part[2]:  # Has time component
            date_clean = '-'.join(date_part).strip()
            return datetime.strptime(date_clean, "%Y-%m-%d %H:%M:%S")
        else:
            # Fallback: split by space and take first two parts
            parts = date_str.split()
            if len(parts) >= 2:
                date_time = f"{parts[0]} {parts[1]}"
                return datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")
            return datetime.now()
    
    def generate_report(self, changes: List[Dict]) -> str:
        """Generate a human-readable report of version changes."""
        if not changes:
            return "No version changes found for @transferwise/components in the specified time range."
        
        report = []
        report.append("=" * 100)
        report.append(f"Version History Report for {self.package_name}")
        report.append("=" * 100)
        report.append("")
        
        # Summary statistics
        report.append("## Summary")
        report.append(f"- Total version changes: {len(changes)}")
        if changes:
            first_date = self.parse_git_date(changes[0]["date"])
            last_date = self.parse_git_date(changes[-1]["date"])
            days_span = (last_date - first_date).days
            report.append(f"- Time span: {days_span} days")
            report.append(f"- Average days between updates: {days_span / len(changes):.1f}" if len(changes) > 1 else "")
        report.append("")
        
        # Detailed changes
        report.append("## Detailed Version Changes")
        report.append("-" * 100)
        
        for i, change in enumerate(changes, 1):
            report.append(f"\n### Change #{i}")
            report.append(f"Date:      {change['date']}")
            report.append(f"Commit:    {change['commit']}")
            report.append(f"Author:    {change['author']}")
            report.append(f"Message:   {change['message']}")
            report.append(f"Effective: {change['previous_effective']} → {change['effective_version']}")
            
            if change['override_version']:
                report.append(f"Override:  {change['override_version']}")
            if change['dependency_version']:
                report.append(f"Dependency: {change['dependency_version']}")
            
            # Calculate days since last change
            if i > 1:
                prev_date = self.parse_git_date(changes[i-2]["date"])
                curr_date = self.parse_git_date(change["date"])
                days_since_last = (curr_date - prev_date).days
                report.append(f"Days since last update: {days_since_last}")
        
        report.append("\n" + "=" * 100)
        
        # Version adoption timeline
        report.append("\n## Version Adoption Timeline")
        report.append("-" * 100)
        
        version_durations = []
        for i in range(len(changes)):
            start_date = self.parse_git_date(changes[i]["date"])
            if i < len(changes) - 1:
                end_date = self.parse_git_date(changes[i+1]["date"])
                duration = (end_date - start_date).days
            else:
                end_date = datetime.now()
                duration = (end_date - start_date).days
                
            version_durations.append({
                "version": changes[i]["effective_version"],
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d") if i < len(changes) - 1 else "current",
                "days": duration
            })
        
        for vd in version_durations:
            report.append(f"{vd['version']:20} | {vd['start']} to {vd['end']:10} | {vd['days']:4} days")
        
        return "\n".join(report)
    
    def save_to_json(self, changes: List[Dict], filename: str = "component_version_history.json"):
        """Save the version history to a JSON file for further analysis."""
        output_path = Path(filename)
        with open(output_path, "w") as f:
            json.dump({
                "package": self.package_name,
                "repository": str(self.repo_path),
                "generated_at": datetime.now().isoformat(),
                "changes": changes
            }, f, indent=2)
        print(f"Saved detailed history to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Track @transferwise/components version history")
    parser.add_argument("--repo", default=".", help="Repository path (default: current directory)")
    parser.add_argument("--months", type=int, default=12, help="Number of months to look back (default: 12)")
    parser.add_argument("--output", help="Output JSON file name (optional)")
    parser.add_argument("--package", default="@transferwise/components", help="Package name to track")
    
    args = parser.parse_args()
    
    # Calculate date range
    until_date = datetime.now()
    since_date = until_date - timedelta(days=args.months * 30)
    
    print(f"Analyzing repository: {Path(args.repo).resolve()}")
    print(f"Tracking package: {args.package}")
    print(f"Date range: {since_date.strftime('%Y-%m-%d')} to {until_date.strftime('%Y-%m-%d')}")
    print("-" * 50)
    
    # Track version changes
    tracker = ComponentVersionTracker(args.repo, args.package)
    changes = tracker.track_version_changes(since_date, until_date)
    
    # Generate and print report
    report = tracker.generate_report(changes)
    print(report)
    
    # Save to JSON if requested
    if args.output:
        tracker.save_to_json(changes, args.output)
    elif changes:
        # Always save JSON for detailed analysis
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"component_versions_{timestamp}.json"
        tracker.save_to_json(changes, default_filename)
    
    return 0 if changes else 1


if __name__ == "__main__":
    sys.exit(main())

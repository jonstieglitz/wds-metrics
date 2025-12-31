#!/usr/bin/env python3
"""
Extract @transferwise/components release versions and dates from the neptune-web repository.
This gives us the actual release dates rather than adoption dates.
"""

import subprocess
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
import argparse
import csv
import re


class ComponentReleaseExtractor:
    """Extract component release information from neptune-web repository."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / '.git').exists():
            raise ValueError(f"{repo_path} is not a git repository")
        
    def get_all_tags(self, since_date: datetime) -> list:
        """Get all git tags with their dates."""
        try:
            # Get tags with dates
            # Format: refname, taggerdate (or committerdate if no tag date)
            cmd = [
                "git", "for-each-ref", 
                "--sort=-version:refname",
                "--format=%(refname:short)|%(taggerdate:iso8601)|%(committerdate:iso8601)",
                "refs/tags"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.repo_path,
                check=True
            )
            
            tags = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                    
                parts = line.split('|')
                if len(parts) >= 2:
                    tag = parts[0]
                    # Use tagger date if available, otherwise committer date
                    date_str = parts[1] if parts[1] else parts[2]
                    
                    if date_str:
                        # Parse the date
                        try:
                            # Handle various date formats
                            if 'T' in date_str:
                                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            else:
                                # Fallback for other formats
                                date_parts = date_str.split()
                                if len(date_parts) >= 2:
                                    date_obj = datetime.strptime(f"{date_parts[0]} {date_parts[1]}", "%Y-%m-%d %H:%M:%S")
                                else:
                                    continue
                            
                            # Check if within date range
                            if date_obj >= since_date:
                                tags.append({
                                    'tag': tag,
                                    'date': date_obj,
                                    'date_str': date_obj.strftime("%Y-%m-%d %H:%M:%S")
                                })
                        except (ValueError, IndexError) as e:
                            print(f"Warning: Could not parse date for tag {tag}: {date_str}")
                            continue
            
            return sorted(tags, key=lambda x: x['date'], reverse=True)
            
        except subprocess.CalledProcessError as e:
            print(f"Error getting tags: {e}")
            return []
    
    def filter_component_tags(self, tags: list) -> list:
        """Filter tags to only include component versions."""
        component_tags = []
        
        for tag_info in tags:
            tag = tag_info['tag']
            
            # Common patterns for component versions:
            # - @transferwise/components@46.115.0
            # - components@46.115.0
            # - v46.115.0
            # - 46.115.0
            
            version = None
            
            # Check various patterns
            if '@transferwise/components@' in tag:
                version = tag.split('@transferwise/components@')[1]
            elif 'components@' in tag:
                version = tag.split('components@')[1]
            elif tag.startswith('v') and re.match(r'v\d+\.\d+\.\d+', tag):
                version = tag[1:]  # Remove 'v' prefix
            elif re.match(r'^\d+\.\d+\.\d+', tag):
                version = tag
            
            if version:
                # Clean version (remove any suffixes like -alpha, -beta)
                clean_version = re.match(r'^(\d+\.\d+\.\d+)', version)
                if clean_version:
                    component_tags.append({
                        'version': clean_version.group(1),
                        'full_version': version,
                        'tag': tag_info['tag'],
                        'date': tag_info['date'],
                        'date_str': tag_info['date_str']
                    })
        
        return component_tags
    
    def get_package_json_versions(self, since_date: datetime) -> list:
        """Alternative: Get versions from package.json history."""
        versions = []
        
        # Get commits that modified package.json
        cmd = [
            "git", "log", 
            "--format=%H|%ai",
            f"--since={since_date.isoformat()}",
            "--", "packages/components/package.json"  # Adjust path as needed
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.repo_path,
                check=True
            )
            
            commits = result.stdout.strip().split('\n')
            seen_versions = set()
            
            for commit_line in commits:
                if not commit_line:
                    continue
                    
                parts = commit_line.split('|')
                if len(parts) != 2:
                    continue
                    
                commit_hash = parts[0]
                date_str = parts[1]
                
                # Get package.json at this commit
                pkg_cmd = ["git", "show", f"{commit_hash}:packages/components/package.json"]
                
                try:
                    pkg_result = subprocess.run(
                        pkg_cmd,
                        capture_output=True,
                        text=True,
                        cwd=self.repo_path,
                        check=True
                    )
                    
                    package_data = json.loads(pkg_result.stdout)
                    version = package_data.get('version')
                    
                    if version and version not in seen_versions:
                        seen_versions.add(version)
                        date_obj = datetime.strptime(date_str.split()[0] + " " + date_str.split()[1], 
                                                    "%Y-%m-%d %H:%M:%S")
                        versions.append({
                            'version': version,
                            'full_version': version,
                            'date': date_obj,
                            'date_str': date_obj.strftime("%Y-%m-%d %H:%M:%S"),
                            'commit': commit_hash[:8]
                        })
                        
                except (subprocess.CalledProcessError, json.JSONDecodeError):
                    continue
            
            return sorted(versions, key=lambda x: x['date'], reverse=True)
            
        except subprocess.CalledProcessError:
            return []
    
    def generate_report(self, versions: list) -> str:
        """Generate a human-readable report of versions."""
        if not versions:
            return "No versions found in the specified time range."
        
        report = []
        report.append("=" * 80)
        report.append("@transferwise/components Release History")
        report.append("=" * 80)
        report.append("")
        report.append(f"Total versions found: {len(versions)}")
        report.append(f"Date range: {versions[-1]['date_str']} to {versions[0]['date_str']}")
        report.append("")
        report.append("Version".ljust(20) + "Release Date".ljust(25) + "Days Since Previous")
        report.append("-" * 70)
        
        for i, version in enumerate(versions):
            days_since = ""
            if i < len(versions) - 1:
                days_diff = (version['date'] - versions[i + 1]['date']).days
                days_since = f"{days_diff} days"
            
            report.append(f"{version['version'].ljust(20)}{version['date_str'].ljust(25)}{days_since}")
        
        # Calculate statistics
        if len(versions) > 1:
            report.append("")
            report.append("## Statistics")
            report.append("-" * 70)
            
            # Calculate average days between releases
            total_days = (versions[0]['date'] - versions[-1]['date']).days
            avg_days = total_days / (len(versions) - 1)
            report.append(f"Average days between releases: {avg_days:.1f}")
            
            # Find longest and shortest gaps
            gaps = []
            for i in range(len(versions) - 1):
                gap = (versions[i]['date'] - versions[i + 1]['date']).days
                gaps.append((gap, versions[i]['version'], versions[i + 1]['version']))
            
            if gaps:
                longest = max(gaps, key=lambda x: x[0])
                shortest = min(gaps, key=lambda x: x[0])
                report.append(f"Longest gap: {longest[0]} days (between {longest[2]} and {longest[1]})")
                report.append(f"Shortest gap: {shortest[0]} days (between {shortest[2]} and {shortest[1]})")
        
        return "\n".join(report)
    
    def export_to_csv(self, versions: list, filename: str = None):
        """Export versions to CSV."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"component_releases_{timestamp}.csv"
        
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['version', 'release_date', 'days_since_previous']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for i, version in enumerate(versions):
                days_since = None
                if i < len(versions) - 1:
                    days_since = (version['date'] - versions[i + 1]['date']).days
                
                writer.writerow({
                    'version': version['version'],
                    'release_date': version['date_str'],
                    'days_since_previous': days_since
                })
        
        print(f"📊 Exported to {filename}")
        return filename
    
    def export_to_json(self, versions: list, filename: str = None):
        """Export versions to JSON."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"component_releases_{timestamp}.json"
        
        output = {
            "package": "@transferwise/components",
            "source_repository": str(self.repo_path),
            "generated_at": datetime.now().isoformat(),
            "versions": [
                {
                    "version": v['version'],
                    "release_date": v['date'].isoformat(),
                    "tag": v.get('tag', ''),
                    "commit": v.get('commit', '')
                }
                for v in versions
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"💾 Exported to {filename}")
        return filename


def main():
    parser = argparse.ArgumentParser(
        description="Extract @transferwise/components release history from neptune-web repository"
    )
    parser.add_argument(
        "--repo",
        default="/Users/jonathan.stieglitz/Code/neptune-web",
        help="Path to neptune-web repository"
    )
    parser.add_argument(
        "--years",
        type=int,
        default=3,
        help="Number of years to look back (default: 3)"
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Export to CSV"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Export to JSON"
    )
    parser.add_argument(
        "--use-commits",
        action="store_true",
        help="Extract versions from package.json commits instead of tags"
    )
    
    args = parser.parse_args()
    
    # Calculate date range
    since_date = datetime.now() - timedelta(days=args.years * 365)
    
    print(f"Extracting @transferwise/components versions from: {args.repo}")
    print(f"Looking back {args.years} years (since {since_date.strftime('%Y-%m-%d')})")
    print("-" * 50)
    
    try:
        extractor = ComponentReleaseExtractor(args.repo)
        
        if args.use_commits:
            print("Using package.json commit history...")
            versions = extractor.get_package_json_versions(since_date)
        else:
            print("Using git tags...")
            tags = extractor.get_all_tags(since_date)
            print(f"Found {len(tags)} tags total")
            
            versions = extractor.filter_component_tags(tags)
            
            if not versions:
                print("\nNo component-specific tags found, trying package.json history...")
                versions = extractor.get_package_json_versions(since_date)
        
        if versions:
            print(f"Found {len(versions)} component versions")
            print()
            
            # Generate report
            report = extractor.generate_report(versions)
            print(report)
            
            # Export if requested
            if args.csv:
                extractor.export_to_csv(versions)
            
            if args.json or True:  # Always save JSON
                extractor.export_to_json(versions)
        else:
            print("No versions found. The repository might use a different structure.")
            print("Try running with --use-commits flag to extract from package.json history.")
            
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

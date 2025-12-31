#!/usr/bin/env python3
"""
Analyze adoption patterns for @transferwise/components comparing release dates with adoption dates.
Generates interactive HTML dashboard with timeline charts and detailed comparison metrics.

Repositories are configured in the REPO_NAMES constant below.
"""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import sys
import argparse
import csv
from typing import Dict, List, Optional, Tuple
import statistics


# Repository configuration - define repo names once
REPO_NAMES = [
    'account-page',
    'account-spend-web',
    'balance-flows-web',
    'balance-pages',
    'batch-payments-flow',
    'bills-page',
    'bulk-send-flow',
    'business-onboarding',
    'card-form',
    'hat-contact-form',
    'multi-currency-account-homepage',
    'partner-integration-flow',
    'recipients-page',
    'request-payer-page',
    'send-flow',
    'twcard-order-web',
]

# Base paths
CODE_BASE_PATH = Path("/Users/jonathan.stieglitz/Code")
GITHUB_BASE_URL = "https://github.com/transferwise"


class AdoptionAnalyzer:
    """Analyze adoption patterns by comparing releases with actual adoption."""
    
    def __init__(self, package_name: str = "@transferwise/components"):
        self.package_name = package_name
        self.releases = {}
        self.repo_adoptions = {}
        # Generate GitHub URLs from repo names
        self.repo_github_urls = {
            repo_name: f"{GITHUB_BASE_URL}/{repo_name}"
            for repo_name in REPO_NAMES
        }
        
    def load_releases(self, releases_file: str):
        """Load release data from JSON file."""
        with open(releases_file, 'r') as f:
            data = json.load(f)
            for version_info in data['versions']:
                version = version_info['version']
                # Normalize version (remove ^ if present)
                clean_version = version.lstrip('^~')
                release_date = datetime.fromisoformat(version_info['release_date'])
                self.releases[clean_version] = {
                    'date': release_date,
                    'version': version
                }
        print(f"Loaded {len(self.releases)} releases")
    
    def get_repo_adoptions(self, repo_path: Path, months: int = 36):
        """Extract adoption history for a repository."""
        repo_name = repo_path.name
        since_date = datetime.now() - timedelta(days=months * 30)
        
        # Get commits that modified package.json
        cmd = [
            "git", "log", "--format=%H|%ai", "--reverse",
            f"--since={since_date.isoformat()}",
            "--", "package.json"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=repo_path,
                check=True
            )
            
            commits = result.stdout.strip().split('\n')
            commits = [c for c in commits if c]
            
            adoptions = []
            last_version = None
            
            for commit_line in commits:
                if not commit_line:
                    continue
                
                parts = commit_line.split('|')
                if len(parts) != 2:
                    continue
                
                commit_hash = parts[0]
                date_str = parts[1]
                
                # Parse date
                date_obj = datetime.strptime(
                    date_str.split()[0] + " " + date_str.split()[1],
                    "%Y-%m-%d %H:%M:%S"
                )
                
                # Get package.json at this commit
                version = self.get_version_at_commit(repo_path, commit_hash)
                
                if version and version != last_version:
                    clean_version = version.lstrip('^~')
                    adoptions.append({
                        'version': clean_version,
                        'raw_version': version,
                        'adoption_date': date_obj,
                        'commit': commit_hash[:8]
                    })
                    last_version = version
            
            self.repo_adoptions[repo_name] = adoptions
            return adoptions
            
        except subprocess.CalledProcessError as e:
            print(f"Error processing {repo_name}: {e}")
            return []
    
    def get_version_at_commit(self, repo_path: Path, commit_hash: str) -> Optional[str]:
        """Get package version at specific commit."""
        try:
            result = subprocess.run(
                ["git", "show", f"{commit_hash}:package.json"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                check=True
            )
            
            package_json = json.loads(result.stdout)
            
            # Check all possible locations
            version = None
            
            # Direct dependency
            if "dependencies" in package_json:
                version = package_json["dependencies"].get(self.package_name)
            
            # pnpm overrides
            if not version and "pnpm" in package_json and "overrides" in package_json["pnpm"]:
                overrides = package_json["pnpm"]["overrides"]
                version = overrides.get(self.package_name)
                
                # Check transitive overrides
                if not version:
                    for key, value in overrides.items():
                        if ">" in key and key.endswith(f">{self.package_name}"):
                            version = value
                            break
            
            return version
            
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None
    
    def calculate_adoption_metrics(self):
        """Calculate detailed adoption metrics."""
        metrics = {}
        
        for repo_name, adoptions in self.repo_adoptions.items():
            repo_metrics = {
                'total_updates': len(adoptions),
                'versions': [],
                'adoption_lags': [],
                'skip_counts': [],
                'update_intervals': []
            }
            
            for i, adoption in enumerate(adoptions):
                version = adoption['version']
                adoption_date = adoption['adoption_date']
                
                # Find release date
                if version in self.releases:
                    release_date = self.releases[version]['date']
                    lag_days = (adoption_date - release_date).days
                    
                    version_info = {
                        'version': version,
                        'release_date': release_date.isoformat(),
                        'adoption_date': adoption_date.isoformat(),
                        'lag_days': lag_days,
                        'commit': adoption['commit']
                    }
                    
                    # Calculate versions skipped
                    if i > 0:
                        prev_version = adoptions[i-1]['version']
                        skipped = self.count_versions_between(prev_version, version)
                        version_info['versions_skipped'] = skipped
                        repo_metrics['skip_counts'].append(skipped)
                        
                        # Calculate days since last update
                        prev_date = adoptions[i-1]['adoption_date']
                        update_interval = (adoption_date - prev_date).days
                        version_info['days_since_last_update'] = update_interval
                        repo_metrics['update_intervals'].append(update_interval)
                    
                    repo_metrics['versions'].append(version_info)
                    repo_metrics['adoption_lags'].append(lag_days)
            
            # Calculate statistics
            if repo_metrics['adoption_lags']:
                repo_metrics['avg_lag_days'] = statistics.mean(repo_metrics['adoption_lags'])
                repo_metrics['median_lag_days'] = statistics.median(repo_metrics['adoption_lags'])
                repo_metrics['min_lag_days'] = min(repo_metrics['adoption_lags'])
                repo_metrics['max_lag_days'] = max(repo_metrics['adoption_lags'])
            
            if repo_metrics['skip_counts']:
                repo_metrics['avg_versions_skipped'] = statistics.mean(repo_metrics['skip_counts'])
                
            if repo_metrics['update_intervals']:
                repo_metrics['avg_update_interval'] = statistics.mean(repo_metrics['update_intervals'])
            
            metrics[repo_name] = repo_metrics
        
        return metrics
    
    def count_versions_between(self, version1: str, version2: str) -> int:
        """Count how many versions were released between two versions."""
        # Get sorted list of all versions
        all_versions = sorted(self.releases.keys(), key=lambda v: self.parse_version(v))
        
        try:
            idx1 = all_versions.index(version1)
            idx2 = all_versions.index(version2)
            return abs(idx2 - idx1) - 1
        except ValueError:
            return 0
    
    def parse_version(self, version: str) -> tuple:
        """Parse version for sorting."""
        parts = version.split('.')
        try:
            return tuple(int(p) for p in parts[:3])
        except (ValueError, IndexError):
            return (0, 0, 0)

    def generate_dashboard_data_json(self, metrics: Dict, filename: str = "adoption_data.json"):
        data = {
            'generated_at': datetime.now().isoformat(timespec='minutes'),
            'repo_github_urls': self.repo_github_urls,
            'releases': {
                version: {
                    'date': release_info['date'].strftime('%Y-%m-%d'),
                    'version': release_info['version']
                }
                for version, release_info in self.releases.items()
            },
            'repo_adoptions': {
                repo_name: [
                    {
                        'version': a['version'],
                        'raw_version': a.get('raw_version', a['version']),
                        'adoption_date': a['adoption_date'].strftime('%Y-%m-%d'),
                        'commit': a.get('commit', ''),
                        'lag_days': (
                            (a['adoption_date'] - self.releases[a['version']]['date']).days
                            if a['version'] in self.releases
                            else None
                        )
                    }
                    for a in adoptions
                ]
                for repo_name, adoptions in self.repo_adoptions.items()
            },
            'metrics': metrics
        }

        with open(filename, 'w') as f:
            json.dump(data, f)

        print(f"📊 Dashboard data saved to {filename}")
        return filename
    
    def generate_timeline_csv(self, filename: str = None):
        """Generate CSV for timeline visualization."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"adoption_timeline_{timestamp}.csv"
        
        rows = []
        
        # Add all releases
        for version, release_info in self.releases.items():
            rows.append({
                'date': release_info['date'].strftime('%Y-%m-%d'),
                'event_type': 'release',
                'version': version,
                'repository': 'neptune-web',
                'lag_days': 0,
                'notes': 'Component released'
            })
        
        # Add all adoptions
        for repo_name, adoptions in self.repo_adoptions.items():
            for adoption in adoptions:
                version = adoption['version']
                if version in self.releases:
                    release_date = self.releases[version]['date']
                    lag = (adoption['adoption_date'] - release_date).days
                    
                    rows.append({
                        'date': adoption['adoption_date'].strftime('%Y-%m-%d'),
                        'event_type': 'adoption',
                        'version': version,
                        'repository': repo_name,
                        'lag_days': lag,
                        'notes': f"Adopted after {lag} days"
                    })
        
        # Sort by date
        rows.sort(key=lambda x: x['date'])
        
        # Write CSV
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['date', 'event_type', 'version', 'repository', 'lag_days', 'notes']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"📊 Timeline CSV saved to {filename}")
        return filename
    
    def generate_comparison_csv(self, metrics: Dict, filename: str = None):
        """Generate CSV comparing the two repositories."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"repo_comparison_{timestamp}.csv"
        
        rows = []
        
        for repo_name, repo_metrics in metrics.items():
            for version_info in repo_metrics['versions']:
                rows.append({
                    'repository': repo_name,
                    'version': version_info['version'],
                    'release_date': version_info['release_date'][:10],
                    'adoption_date': version_info['adoption_date'][:10],
                    'lag_days': version_info['lag_days'],
                    'versions_skipped': version_info.get('versions_skipped', 0),
                    'days_since_last_update': version_info.get('days_since_last_update', 0)
                })
        
        # Sort by adoption date
        rows.sort(key=lambda x: x['adoption_date'])
        
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['repository', 'version', 'release_date', 'adoption_date', 
                         'lag_days', 'versions_skipped', 'days_since_last_update']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"📊 Comparison CSV saved to {filename}")
        return filename
    
    def generate_html_dashboard(self, metrics: Dict, filename: str = None):
        """Generate an HTML dashboard with charts."""
        if not filename:
            filename = "adoption_dashboard.html"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>@transferwise/components Adoption Analysis</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            margin: 0;
            color: #333;
        }}
        .subtitle {{
            color: #666;
            margin-top: 5px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #2c5282;
        }}
        .metric-label {{
            color: #666;
            margin-top: 5px;
        }}
        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .comparison-table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            table-layout: fixed;
        }}
        .comparison-table th {{
            background: #f7fafc;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #e2e8f0;
            width: auto;
        }}
        .comparison-table th:first-child {{
            width: 250px;
        }}
        .comparison-table th.average-column {{
            background: #edf2f7;
            font-weight: 700;
        }}
        .comparison-table td {{
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .comparison-table td.average-column {{
            background: #f7fafc;
            font-weight: 600;
        }}
        .repo-header {{
            font-weight: 600;
            color: #2c5282;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>@transferwise/components Adoption Analysis</h1>
        <div class="subtitle">Repository Comparison</div>
        <div class="subtitle">Generated: <span id="generatedAt"></span></div>
    </div>
"""
        
        # Create adoption lag chart (hidden for now)
        # html += '<div class="chart-container">'
        # html += '<h2>Adoption Lag Over Time</h2>'
        # html += '<div id="lagChart"></div>'
        # html += '</div>'
        
        lag_chart_data = []
        
        # Add lag chart JavaScript (hidden for now)
        # html += f"""
        # <script>
        # var repoGithubUrls = {json.dumps(self.repo_github_urls)};
        # 
        # // Shared function to handle PR clicks
        # function handlePRClick(point) {{
        #     var customData = point.customdata;
        #     if (customData && customData.commit && customData.repo) {{
        #         var repoUrl = repoGithubUrls[customData.repo];
        #         if (repoUrl) {{
        #             var prUrl = repoUrl + '/pulls?q=is%3Apr+' + customData.commit;
        #             window.open(prUrl, '_blank');
        #         }}
        #     }}
        # }}
        # 
        # var lagData = {json.dumps(lag_chart_data)};
        # var traces = lagData.map(repo => ({{
        #     x: repo.x,
        #     y: repo.y,
        #     text: repo.text,
        #     customdata: repo.commits.map((commit, idx) => ({{
        #         commit: commit,
        #         repo: repo.name,
        #         version: repo.text[idx]
        #     }})),
        #     name: repo.name,
        #     type: 'scatter',
        #     mode: 'lines+markers',
        #     hovertemplate: '<b>%{{text}}</b><br>Lag: %{{y}} days<extra></extra>'
        # }}));
        # 
        # Plotly.newPlot('lagChart', traces, {{
        #     title: '',
        #     xaxis: {{ title: '' }},
        #     yaxis: {{ title: 'Adoption Lag (days)' }},
        #     height: 400,
        #     margin: {{ t: 20 }},
        #     hovermode: 'closest'
        # }});
        # 
        # // Add click handler for lag chart
        # document.getElementById('lagChart').on('plotly_click', function(data) {{
        #     handlePRClick(data.points[0]);
        # }});
        # </script>
        # """
        
        # Create version timeline chart
        html += '<div class="chart-container">'
        html += '<h2>Version Adoption Timeline</h2>'
        html += '<div id="repoFilters" style="margin-bottom: 15px;"></div>'
        html += '<div id="timelineChart"></div>'
        html += '</div>'

        script = """
        <script>
        function safeNumber(value) {{
            if (value === null || value === undefined) return null;
            if (typeof value === 'number' && !isNaN(value)) return value;
            return null;
        }}

        function formatDaysPostRelease(value) {{
            var n = safeNumber(value);
            if (n === null) return 'N/A';
            return n + ' days post release';
        }}

        function buildTable(metrics) {{
            var container = document.getElementById('comparisonContainer');

            var table = document.createElement('table');
            table.className = 'comparison-table';

            var thead = document.createElement('thead');
            var headerRow = document.createElement('tr');
            var thMetric = document.createElement('th');
            thMetric.textContent = 'Metric';
            headerRow.appendChild(thMetric);

            var sortedRepos = Object.keys(metrics).sort();
            sortedRepos.forEach(function(repoName) {{
                var th = document.createElement('th');
                var shortName = repoName.replace('-web', '').replace(/-/g, ' ');
                th.textContent = shortName.replace(/\b\w/g, function(c) {{ return c.toUpperCase(); }});
                headerRow.appendChild(th);
            }});

            var thAll = document.createElement('th');
            thAll.className = 'average-column';
            thAll.textContent = 'All Repos';
            headerRow.appendChild(thAll);
            thead.appendChild(headerRow);
            table.appendChild(thead);

            var metricNames = [
                ['total_updates', 'Total Updates'],
                ['avg_lag_days', 'Average Adoption Lag (days)'],
                ['max_lag_days', 'Slowest Adoption (days)'],
                ['avg_versions_skipped', 'Avg Versions Skipped'],
                ['avg_update_interval', 'Avg Days Between Updates']
            ];

            var allAdoptionLags = [];
            var allSkipCounts = [];
            var allUpdateIntervals = [];
            var totalUpdatesSum = 0;
            var maxLagOverall = null;

            sortedRepos.forEach(function(repoName) {{
                var repoData = metrics[repoName] || {{}};
                if (Array.isArray(repoData.adoption_lags)) allAdoptionLags = allAdoptionLags.concat(repoData.adoption_lags);
                if (Array.isArray(repoData.skip_counts)) allSkipCounts = allSkipCounts.concat(repoData.skip_counts);
                if (Array.isArray(repoData.update_intervals)) allUpdateIntervals = allUpdateIntervals.concat(repoData.update_intervals);
                totalUpdatesSum += (repoData.total_updates || 0);

                var repoMax = safeNumber(repoData.max_lag_days);
                if (repoMax !== null) {{
                    if (maxLagOverall === null || repoMax > maxLagOverall) maxLagOverall = repoMax;
                }}
            }});

            function mean(arr) {{
                if (!arr.length) return null;
                var s = arr.reduce(function(a, b) {{ return a + b; }}, 0);
                return s / arr.length;
            }}

            var tbody = document.createElement('tbody');
            metricNames.forEach(function(pair) {{
                var metricKey = pair[0];
                var metricLabel = pair[1];

                var tr = document.createElement('tr');
                var tdLabel = document.createElement('td');
                tdLabel.textContent = metricLabel;
                tr.appendChild(tdLabel);

                sortedRepos.forEach(function(repoName) {{
                    var value = metrics[repoName] ? metrics[repoName][metricKey] : null;
                    var td = document.createElement('td');
                    if (value === null || value === undefined || value === 'N/A') {{
                        td.textContent = 'N/A';
                    }} else if (typeof value === 'number' && !isNaN(value)) {{
                        td.textContent = (Number.isInteger(value) ? value.toString() : value.toFixed(1));
                    }} else {{
                        td.textContent = value;
                    }}
                    tr.appendChild(td);
                }});

                var tdAll = document.createElement('td');
                tdAll.className = 'average-column';

                if (metricKey === 'total_updates') {{
                    tdAll.textContent = totalUpdatesSum.toString();
                }} else if (metricKey === 'avg_lag_days') {{
                    var overallAvg = mean(allAdoptionLags);
                    tdAll.textContent = overallAvg === null ? 'N/A' : overallAvg.toFixed(1);
                }} else if (metricKey === 'max_lag_days') {{
                    tdAll.textContent = maxLagOverall === null ? 'N/A' : maxLagOverall.toString();
                }} else if (metricKey === 'avg_versions_skipped') {{
                    var overallAvgSkip = mean(allSkipCounts);
                    tdAll.textContent = overallAvgSkip === null ? 'N/A' : overallAvgSkip.toFixed(1);
                }} else if (metricKey === 'avg_update_interval') {{
                    var overallAvgInterval = mean(allUpdateIntervals);
                    tdAll.textContent = overallAvgInterval === null ? 'N/A' : overallAvgInterval.toFixed(1);
                }}

                tr.appendChild(tdAll);
                tbody.appendChild(tr);
            }});

            table.appendChild(tbody);
            container.innerHTML = '';
            container.appendChild(table);
        }

        function renderDashboard(dashboard) {{
            var generatedAtEl = document.getElementById('generatedAt');
            if (generatedAtEl) generatedAtEl.textContent = dashboard.generated_at || '';

            var repoGithubUrls = dashboard.repo_github_urls || {{}};

            function handlePRClick(point) {{
                var customData = point.customdata;
                if (customData && customData.commit && customData.repo) {{
                    var repoUrl = repoGithubUrls[customData.repo];
                    if (repoUrl) {{
                        var prUrl = repoUrl + '/pulls?q=is%3Apr+' + customData.commit;
                        window.open(prUrl, '_blank');
                    }}
                }}
            }}

            var repoAdoptions = dashboard.repo_adoptions || {{}};
            var releasesMap = dashboard.releases || {{}};
            var metrics = dashboard.metrics || {{}};

            var repoNames = Object.keys(repoAdoptions).sort();
            var colorPalette = [
                '#3182ce', '#ed8936', '#48bb78', '#9f7aea', '#e53e3e', '#38b2ac',
                '#dd6b20', '#d69e2e', '#805ad5', '#319795', '#2c5282', '#c05621',
                '#2f855a', '#6b46c1', '#c53030', '#2d3748', '#1a365d', '#744210',
                '#22543d', '#553c9a', '#9b2c2c', '#4a5568', '#2c7a7b', '#975a16',
                '#276749', '#44337a', '#742a2a', '#718096', '#285e61', '#7c2d12',
                '#1c4532', '#322659'
            ];

            var colors = {{}};
            repoNames.forEach(function(repoName, idx) {{
                colors[repoName] = colorPalette[idx % colorPalette.length];
            }});

            var timelineData = [];
            repoNames.forEach(function(repoName) {{
                (repoAdoptions[repoName] || []).forEach(function(a) {{
                    timelineData.push({
                        repo: repoName,
                        date: a.adoption_date,
                        version: a.version,
                        color: colors[repoName] || '#718096',
                        commit: a.commit || '',
                        lag_days: a.lag_days
                    });
                }});
            }});

            var releaseData = Object.keys(releasesMap).map(function(version) {{
                return {{
                    version: version,
                    date: releasesMap[version].date
                }};
            }});

            var repoGroups = {{}};
            timelineData.forEach(function(d) {{
                if (!repoGroups[d.repo]) repoGroups[d.repo] = {{x: [], y: [], text: [], commits: [], lags: [], color: d.color}};
                repoGroups[d.repo].x.push(d.date);
                repoGroups[d.repo].y.push(d.repo);
                repoGroups[d.repo].text.push(d.version);
                repoGroups[d.repo].commits.push(d.commit);
                repoGroups[d.repo].lags.push(d.lag_days);
            }});

            var timelineTraces = Object.keys(repoGroups).map(function(repo) {{
                return {{
                    x: repoGroups[repo].x,
                    y: repoGroups[repo].y,
                    text: repoGroups[repo].text,
                    customdata: repoGroups[repo].commits.map(function(commit, idx) {{
                        return {{
                            commit: commit,
                            repo: repo,
                            version: repoGroups[repo].text[idx],
                            lag_days: repoGroups[repo].lags[idx]
                        }};
                    }),
                    name: repo,
                    type: 'scatter',
                    mode: 'markers',
                    marker: {
                        size: 12,
                        color: repoGroups[repo].color
                    },
                    hovertemplate: '<b>%{{text}}</b><br>%{{x}}<br>%{{customdata.lag_days}} days post release<extra></extra>'
                }};
            }});

            var releaseTrace = {
                x: releaseData.map(function(r) {{ return r.date; }}),
                y: Array(releaseData.length).fill('Releases'),
                text: releaseData.map(function(r) {{ return r.version; }}),
                customdata: releaseData.map(function(r) {{ return {{ version: r.version }}; }}),
                name: 'Releases',
                type: 'scatter',
                mode: 'markers',
                marker: {
                    size: 8,
                    color: '#9CA3AF',
                    opacity: 0.6
                },
                hovertemplate: '<b>%{{text}}</b><br>Released: %{{x}}<extra></extra>'
            };

            timelineTraces.push(releaseTrace);

            var categoryOrder = ['Releases'].concat(Object.keys(repoGroups).sort());

            var layout = {
                title: '',
                xaxis: { title: 'Date' },
                yaxis: {
                    title: '',
                    fixedrange: true,
                    categoryorder: 'array',
                    categoryarray: categoryOrder,
                    tickfont: { size: 11 }
                },
                height: 1000,
                margin: { t: 20, l: 220 },
                showlegend: false,
                hovermode: 'closest'
            };

            var config = { displayModeBar: false };
            Plotly.newPlot('timelineChart', timelineTraces, layout, config);

            var chartDiv = document.getElementById('timelineChart');
            var filtersDiv = document.getElementById('repoFilters');
            filtersDiv.innerHTML = '<strong>Show repositories:</strong> ';

            var traceNames = Object.keys(repoGroups).sort();
            traceNames.forEach(function(repoName) {
                var label = document.createElement('label');
                label.style.marginRight = '15px';
                label.style.cursor = 'pointer';

                var checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = true;
                checkbox.value = repoName;
                checkbox.style.marginRight = '5px';
                checkbox.style.cursor = 'pointer';

                checkbox.addEventListener('change', function() {
                    var visibleTraces = [];
                    var checkboxes = filtersDiv.querySelectorAll('input[type="checkbox"]');
                    checkboxes.forEach(function(cb) {
                        if (cb.checked) visibleTraces.push(cb.value);
                    });

                    timelineTraces.forEach(function(trace, idx) {
                        if (trace.name === 'Releases') {
                            Plotly.restyle('timelineChart', {'visible': true}, [idx]);
                        } else {
                            var isVisible = visibleTraces.indexOf(trace.name) !== -1;
                            Plotly.restyle('timelineChart', {'visible': isVisible}, [idx]);
                        }
                    });
                });

                label.appendChild(checkbox);
                label.appendChild(document.createTextNode(repoName));
                filtersDiv.appendChild(label);
            });

            var selectAllBtn = document.createElement('button');
            selectAllBtn.textContent = 'Select All';
            selectAllBtn.style.marginLeft = '15px';
            selectAllBtn.style.padding = '2px 8px';
            selectAllBtn.style.cursor = 'pointer';
            selectAllBtn.addEventListener('click', function() {
                var checkboxes = filtersDiv.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(function(cb) {
                    cb.checked = true;
                    cb.dispatchEvent(new Event('change'));
                });
            });

            var deselectAllBtn = document.createElement('button');
            deselectAllBtn.textContent = 'Deselect All';
            deselectAllBtn.style.marginLeft = '5px';
            deselectAllBtn.style.padding = '2px 8px';
            deselectAllBtn.style.cursor = 'pointer';
            deselectAllBtn.addEventListener('click', function() {
                var checkboxes = filtersDiv.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(function(cb) {
                    cb.checked = false;
                    cb.dispatchEvent(new Event('change'));
                });
            });

            filtersDiv.appendChild(selectAllBtn);
            filtersDiv.appendChild(deselectAllBtn);

            chartDiv.on('plotly_hover', function(data) {
                var point = data.points[0];
                if (point.data.name !== 'Releases') {
                    var version = point.text;
                    var releaseTraceIndex = timelineTraces.length - 1;
                    var releaseIndex = releaseData.findIndex(function(r) { return r.version === version; });

                    if (releaseIndex !== -1) {
                        var numReleases = releaseData.length;
                        var markerColors = new Array(numReleases).fill('#9CA3AF');
                        var opacities = new Array(numReleases).fill(0.6);

                        markerColors[releaseIndex] = '#000000';
                        opacities[releaseIndex] = 1;

                        Plotly.restyle('timelineChart', {
                            'marker.color': [markerColors],
                            'marker.opacity': [opacities]
                        }, [releaseTraceIndex]);
                    }
                }
            });

            chartDiv.on('plotly_unhover', function(data) {
                var releaseTraceIndex = timelineTraces.length - 1;
                var numReleases = releaseData.length;
                Plotly.restyle('timelineChart', {
                    'marker.color': [new Array(numReleases).fill('#9CA3AF')],
                    'marker.opacity': [new Array(numReleases).fill(0.6)]
                }, [releaseTraceIndex]);
            });

            chartDiv.on('plotly_click', function(data) {
                var point = data.points[0];
                if (point.data.name === 'Releases') {
                    var customData = point.customdata;
                    if (customData && customData.version) {
                        var releaseUrl = 'https://github.com/transferwise/neptune-web/releases/tag/@transferwise/components@' + customData.version;
                        window.open(releaseUrl, '_blank');
                    }
                } else {
                    handlePRClick(point);
                }
            });

            buildTable(metrics);
        }

        fetch('adoption_data.json').then(function(res) {
            return res.json();
        }).then(function(dashboard) {
            renderDashboard(dashboard);
        });
        </script>
        """

        html += script.replace('{{', '{').replace('}}', '}')
        
        html += '<div class="chart-container">'
        html += '<h2>Detailed Comparison</h2>'
        html += '<div id="comparisonContainer"></div>'
        html += '</div>'
        
        html += '</body></html>'
        
        with open(filename, 'w') as f:
            f.write(html)
        
        print(f"📊 HTML dashboard saved to {filename}")
        return filename
    
    def generate_insights_report(self, metrics: Dict):
        """Generate detailed insights report."""
        report = []
        report.append("=" * 80)
        report.append("ADOPTION PATTERN ANALYSIS")
        report.append("=" * 80)
        
        for repo_name, repo_metrics in metrics.items():
            report.append(f"\n## {repo_name}")
            report.append("-" * 40)
            
            report.append(f"Total updates: {repo_metrics['total_updates']}")
            
            if repo_metrics.get('avg_lag_days'):
                report.append(f"Average adoption lag: {repo_metrics['avg_lag_days']:.1f} days")
                report.append(f"  - Median: {repo_metrics['median_lag_days']} days")
                report.append(f"  - Fastest: {repo_metrics['min_lag_days']} days")
                report.append(f"  - Slowest: {repo_metrics['max_lag_days']} days")
            
            if repo_metrics.get('avg_versions_skipped'):
                report.append(f"Average versions skipped: {repo_metrics['avg_versions_skipped']:.1f}")
            
            if repo_metrics.get('avg_update_interval'):
                report.append(f"Average update interval: {repo_metrics['avg_update_interval']:.1f} days")
            
            # Show recent adoptions
            if repo_metrics['versions']:
                report.append("\nRecent adoptions:")
                for v in repo_metrics['versions'][-5:]:
                    report.append(f"  {v['version']}: {v['lag_days']} days lag, "
                                f"{v.get('versions_skipped', 0)} versions skipped")
        
        # Comparative insights
        report.append("\n" + "=" * 80)
        report.append("COMPARATIVE INSIGHTS")
        report.append("=" * 80)
        
        if len(metrics) >= 2:
            # Find extremes
            most_updates = max(metrics.items(), key=lambda x: x[1]['total_updates'])
            least_updates = min(metrics.items(), key=lambda x: x[1]['total_updates'])
            
            fastest_adopter = min(metrics.items(), key=lambda x: x[1].get('avg_lag_days', float('inf')))
            slowest_adopter = max(metrics.items(), key=lambda x: x[1].get('avg_lag_days', 0))
            
            most_skipping = max(metrics.items(), key=lambda x: x[1].get('avg_versions_skipped', 0))
            least_skipping = min(metrics.items(), key=lambda x: x[1].get('avg_versions_skipped', float('inf')))
            
            # Report findings
            report.append(f"\n📊 Update Frequency:")
            report.append(f"  Most frequent: {most_updates[0]} ({most_updates[1]['total_updates']} updates)")
            report.append(f"  Least frequent: {least_updates[0]} ({least_updates[1]['total_updates']} updates)")
            if most_updates[1]['total_updates'] > 0 and least_updates[1]['total_updates'] > 0:
                ratio = most_updates[1]['total_updates'] / least_updates[1]['total_updates']
                report.append(f"  Ratio: {ratio:.1f}x difference")
            
            report.append(f"\n⚡ Adoption Speed:")
            report.append(f"  Fastest: {fastest_adopter[0]} ({fastest_adopter[1].get('avg_lag_days', 0):.1f} days)")
            report.append(f"  Slowest: {slowest_adopter[0]} ({slowest_adopter[1].get('avg_lag_days', 0):.1f} days)")
            
            report.append(f"\n🎯 Version Selection:")
            report.append(f"  Most selective: {most_skipping[0]} (skips {most_skipping[1].get('avg_versions_skipped', 0):.1f} versions)")
            report.append(f"  Least selective: {least_skipping[0]} (skips {least_skipping[1].get('avg_versions_skipped', 0):.1f} versions)")
            
            # Rank repos by update frequency
            report.append(f"\n📈 Repository Rankings by Update Frequency:")
            ranked = sorted(metrics.items(), key=lambda x: x[1]['total_updates'], reverse=True)
            for i, (repo, data) in enumerate(ranked, 1):
                interval = data.get('avg_update_interval', 0)
                report.append(f"  {i}. {repo}: {data['total_updates']} updates (every {interval:.1f} days)")
        
        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Analyze adoption patterns for @transferwise/components")
    parser.add_argument("--releases", 
                       default="component_releases_20251218_130049.json",
                       help="JSON file with release data")
    parser.add_argument("--months", type=int, default=36,
                       help="Number of months to analyze")
    
    args = parser.parse_args()
    
    analyzer = AdoptionAnalyzer()
    
    # Load release data
    print("Loading release data...")
    analyzer.load_releases(args.releases)
    
    # Generate repository paths from REPO_NAMES constant
    repos = [CODE_BASE_PATH / repo_name for repo_name in REPO_NAMES]
    
    # Filter to only repos that exist
    existing_repos = [repo for repo in repos if repo.exists()]
    missing_repos = [repo for repo in repos if not repo.exists()]
    
    if missing_repos:
        print(f"\n⚠️  Skipping {len(missing_repos)} repositories (not found locally):")
        for repo in missing_repos:
            print(f"    - {repo.name}")
    
    print(f"\nAnalyzing {len(existing_repos)} repositories for {args.months} months...")
    for repo in existing_repos:
        print(f"  Processing {repo.name}...")
        analyzer.get_repo_adoptions(repo, args.months)
    
    # Calculate metrics
    print("\nCalculating adoption metrics...")
    metrics = analyzer.calculate_adoption_metrics()
    
    # Generate outputs
    print("\nGenerating outputs...")
    analyzer.generate_timeline_csv()
    analyzer.generate_comparison_csv(metrics)
    analyzer.generate_dashboard_data_json(metrics)
    analyzer.generate_html_dashboard(metrics)
    
    # Print insights
    report = analyzer.generate_insights_report(metrics)
    print("\n" + report)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

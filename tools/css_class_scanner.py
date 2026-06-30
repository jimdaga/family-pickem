#!/usr/bin/env python3
"""
CSS Class Scanner - Extracts and categorizes all CSS classes from Django templates
"""
import re
import json
from pathlib import Path
from collections import defaultdict

class CSSClassScanner:
    def __init__(self, templates_dir, tailwind_css_path):
        self.templates_dir = Path(templates_dir)
        self.tailwind_css_path = Path(tailwind_css_path)
        self.results = {
            'tailwind_classes': set(),
            'legacy_classes': set(),
            'bootstrap_classes': set(),
            'unknown_classes': set(),
            'class_usage': defaultdict(list)  # class -> [file1, file2, ...]
        }

    def scan_templates(self):
        """Scan all .html files for CSS classes"""
        html_files = list(self.templates_dir.rglob('*.html'))

        print(f"Found {len(html_files)} template files")

        for html_file in html_files:
            self._scan_file(html_file)

        return self._categorize_classes()

    def _scan_file(self, file_path):
        """Extract classes from a single file"""
        try:
            content = file_path.read_text()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return

        # Match class="..." and class='...'
        class_patterns = [
            r'class="([^"]*)"',
            r"class='([^']*)'",
        ]

        for pattern in class_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                classes = match.group(1).split()
                for cls in classes:
                    # Skip template variables
                    if '{' in cls or '%' in cls or '{{' in cls:
                        continue
                    self.results['class_usage'][cls].append(str(file_path.relative_to(self.templates_dir.parent)))

    def _categorize_classes(self):
        """Categorize classes into Tailwind, Bootstrap, Legacy, Unknown"""
        # Load Tailwind classes from built CSS
        tailwind_classes = self._extract_tailwind_classes()

        # Known Bootstrap patterns
        bootstrap_patterns = [
            r'^(container|row|col|btn|nav|navbar|dropdown|modal|card|alert|badge|form-)',
            r'^(d-|flex-|justify-|align-|mb-|mt-|ms-|me-|p-|px-|py-|text-|bg-)',
            r'-(sm|md|lg|xl|xxl)(-|$)'
        ]

        for cls in self.results['class_usage'].keys():
            # Check if Tailwind
            if cls in tailwind_classes or self._is_tailwind_pattern(cls):
                self.results['tailwind_classes'].add(cls)
            # Check if Bootstrap
            elif any(re.search(pattern, cls) for pattern in bootstrap_patterns):
                self.results['bootstrap_classes'].add(cls)
            # Check if known custom class
            elif self._is_known_legacy_class(cls):
                self.results['legacy_classes'].add(cls)
            else:
                self.results['unknown_classes'].add(cls)

        return self.results

    def _extract_tailwind_classes(self):
        """Extract valid Tailwind classes from built CSS"""
        if not self.tailwind_css_path.exists():
            print(f"Warning: Tailwind CSS not found at {self.tailwind_css_path}")
            return set()

        content = self.tailwind_css_path.read_text()
        # Match class selectors like .class-name
        classes = re.findall(r'\.([\w-]+(?:\/\d+)?)\s*[,{]', content)
        return set(classes)

    def _is_tailwind_pattern(self, cls):
        """Check if class follows Tailwind naming patterns"""
        tailwind_patterns = [
            r'^(text|bg|border|rounded|p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|w|h|flex|grid|gap|space)-',
            r'^(hover|focus|active|dark|sm|md|lg|xl|2xl):',
            r'^space-(x|y)-\d+',
            r'/(10|20|30|40|50|60|70|80|90|95|100)$',
            r'^(items|justify|self|place)-',
            r'^(opacity|z|order|inset|top|bottom|left|right|shadow|ring)-'
        ]
        return any(re.search(pattern, cls) for pattern in tailwind_patterns)

    def _is_known_legacy_class(self, cls):
        """Check against known legacy classes"""
        legacy_prefixes = [
            'stats-', 'performance-', 'stat-', 'position-', 'champion-',
            'quick-', 'player-', 'team-logo', 'team-score', 'team-info', 'team-details',
            'winner-', 'perfect-', 'missed-', 'trend-', 'page-header',
            'progress-', 'game-', 'leaderboard-', 'section-', 'rank-',
            'teams-matchup', 'quarter-score', 'missing-picks', 'winning-team',
            'rule-', 'enforcer-', 'filter-btn'
        ]

        # Check if class starts with any legacy prefix
        for prefix in legacy_prefixes:
            if cls.startswith(prefix) or cls == prefix.rstrip('-'):
                return True

        # Check exact matches for known legacy classes
        legacy_exact = [
            'teams-matchup', 'team-score-row', 'quarter-score', 'game-status',
            'game-status-display', 'winning-team', 'performance-item',
            'performance-label', 'missing-picks-section', 'missing-picks-header',
            'missing-picks-list', 'filter-btn', 'sort-btn'
        ]

        return cls in legacy_exact

    def generate_report(self, output_file='css_migration_scan.json'):
        """Generate JSON report of findings"""
        report = {
            'summary': {
                'total_classes': len(self.results['class_usage']),
                'tailwind_count': len(self.results['tailwind_classes']),
                'bootstrap_count': len(self.results['bootstrap_classes']),
                'legacy_count': len(self.results['legacy_classes']),
                'unknown_count': len(self.results['unknown_classes'])
            },
            'legacy_classes': {
                cls: self.results['class_usage'][cls]
                for cls in sorted(self.results['legacy_classes'])
            },
            'bootstrap_classes': {
                cls: self.results['class_usage'][cls]
                for cls in sorted(self.results['bootstrap_classes'])
            },
            'unknown_classes': {
                cls: self.results['class_usage'][cls]
                for cls in sorted(self.results['unknown_classes'])
            },
            'high_priority_files': self._identify_priority_files()
        }

        Path(output_file).write_text(json.dumps(report, indent=2))
        return report

    def _identify_priority_files(self):
        """Identify files with most legacy/bootstrap classes"""
        file_scores = defaultdict(int)

        for cls in self.results['legacy_classes'] | self.results['bootstrap_classes']:
            for file_path in self.results['class_usage'][cls]:
                file_scores[file_path] += 1

        # Sort by score descending
        return sorted(file_scores.items(), key=lambda x: x[1], reverse=True)

if __name__ == '__main__':
    scanner = CSSClassScanner(
        templates_dir='/Users/jim/git/family-pickem/pickem/pickem_homepage/templates',
        tailwind_css_path='/Users/jim/git/family-pickem/pickem/pickem_homepage/static/css/tailwind.css'
    )

    results = scanner.scan_templates()
    report = scanner.generate_report('css_migration_scan.json')

    print(f"\n{'='*60}")
    print(f"Scan Complete!")
    print(f"{'='*60}")
    print(f"Total classes found: {report['summary']['total_classes']}")
    print(f"Tailwind classes: {report['summary']['tailwind_count']}")
    print(f"Bootstrap classes: {report['summary']['bootstrap_count']}")
    print(f"Legacy classes: {report['summary']['legacy_count']}")
    print(f"Unknown classes: {report['summary']['unknown_count']}")
    print(f"\nTop files needing migration:")
    for file_path, score in report['high_priority_files'][:10]:
        print(f"  {file_path}: {score} legacy/bootstrap classes")
    print(f"\nReport saved to: css_migration_scan.json")

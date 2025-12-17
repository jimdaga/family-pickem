#!/usr/bin/env python3
"""
Legacy CSS Extractor - Parses old CSS files and extracts class definitions
"""
import re
import json
from pathlib import Path
from typing import Dict

class LegacyCSSExtractor:
    def __init__(self, style_css_path, dark_mode_css_path):
        self.style_css = Path(style_css_path)
        self.dark_mode_css = Path(dark_mode_css_path)
        self.class_definitions = {}

    def extract(self):
        """Extract all class definitions from CSS files"""
        # Parse style.css
        if self.style_css.exists():
            print(f"Parsing {self.style_css}...")
            self._parse_css_file(self.style_css, 'light')
        else:
            print(f"Warning: {self.style_css} not found")

        # Parse dark-mode.css
        if self.dark_mode_css.exists():
            print(f"Parsing {self.dark_mode_css}...")
            self._parse_css_file(self.dark_mode_css, 'dark')
        else:
            print(f"Warning: {self.dark_mode_css} not found")

        return self.class_definitions

    def _parse_css_file(self, css_file, mode):
        """Parse a CSS file and extract rules"""
        content = css_file.read_text()

        # Remove comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

        # Match CSS rules: .class { properties }
        # Handle both single-line and multi-line rules
        pattern = r'\.([a-zA-Z0-9_-]+)\s*\{([^}]+)\}'

        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
        class_count = 0

        for match in matches:
            class_name = match.group(1)
            properties = match.group(2).strip()

            if class_name not in self.class_definitions:
                self.class_definitions[class_name] = {
                    'light': {},
                    'dark': {},
                    'properties_raw': {}
                }

            # Parse properties
            props = self._parse_properties(properties)
            self.class_definitions[class_name][mode] = props
            self.class_definitions[class_name]['properties_raw'][mode] = properties
            class_count += 1

        print(f"  Found {class_count} class definitions in {mode} mode")

    def _parse_properties(self, properties_text):
        """Parse CSS properties into key-value pairs"""
        props = {}
        # Split by semicolon, handle multi-line
        declarations = [d.strip() for d in properties_text.split(';') if d.strip()]

        for decl in declarations:
            if ':' in decl:
                key, value = decl.split(':', 1)
                props[key.strip()] = value.strip()

        return props

    def save_to_json(self, output_file='legacy_css_definitions.json'):
        """Save extracted definitions to JSON"""
        output = {
            'total_classes': len(self.class_definitions),
            'classes': self.class_definitions
        }

        Path(output_file).write_text(json.dumps(output, indent=2))
        print(f"\n{'='*60}")
        print(f"Saved {len(self.class_definitions)} class definitions to {output_file}")
        print(f"{'='*60}")

if __name__ == '__main__':
    extractor = LegacyCSSExtractor(
        style_css_path='/Users/jim/git/family-pickem/pickem/pickem_homepage/static/css/style.css',
        dark_mode_css_path='/Users/jim/git/family-pickem/pickem/pickem_homepage/static/css/dark-mode.css'
    )

    extractor.extract()
    extractor.save_to_json()

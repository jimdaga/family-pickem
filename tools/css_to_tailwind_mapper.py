#!/usr/bin/env python3
"""
CSS to Tailwind Mapper - Converts CSS properties to Tailwind classes
"""
import json
import re
from pathlib import Path
from typing import List, Dict

class CSSTailwindMapper:
    def __init__(self, legacy_definitions_file='legacy_css_definitions.json'):
        if not Path(legacy_definitions_file).exists():
            print(f"Error: {legacy_definitions_file} not found. Run extract_legacy_css.py first.")
            self.legacy_defs = {'classes': {}}
        else:
            self.legacy_defs = json.loads(Path(legacy_definitions_file).read_text())

        self.mappings = {}

    def map_all_classes(self):
        """Map all legacy classes to Tailwind"""
        print("Mapping CSS classes to Tailwind...")

        for class_name in self.legacy_defs['classes'].keys():
            self.mappings[class_name] = self.map_class(class_name)

        print(f"Mapped {len(self.mappings)} classes")
        return self.mappings

    def map_class(self, class_name):
        """Map a single legacy class to Tailwind equivalents"""
        if class_name not in self.legacy_defs['classes']:
            return {'error': 'Class not found in legacy definitions'}

        class_def = self.legacy_defs['classes'][class_name]

        light_props = class_def.get('light', {})
        dark_props = class_def.get('dark', {})

        tailwind_classes = {
            'base': [],
            'dark': [],
            'complexity': 'simple',
            'requires_custom_css': False,
            'notes': []
        }

        # Map common properties
        tailwind_classes['base'] = self._map_properties(light_props)
        tailwind_classes['dark'] = self._map_properties(dark_props, dark_mode=True)

        # Determine complexity
        prop_count = len(light_props) + len(dark_props)
        if prop_count > 15 or self._has_complex_properties(light_props):
            tailwind_classes['complexity'] = 'high'
            tailwind_classes['requires_custom_css'] = True
            tailwind_classes['notes'].append('Consider creating custom component class in input.css')
        elif prop_count > 8:
            tailwind_classes['complexity'] = 'medium'

        return tailwind_classes

    def _map_properties(self, props, dark_mode=False):
        """Map CSS properties to Tailwind classes"""
        classes = []
        prefix = 'dark:' if dark_mode else ''

        for prop, value in props.items():
            mapped = self._map_single_property(prop, value, prefix)
            if mapped:
                if isinstance(mapped, list):
                    classes.extend(mapped)
                else:
                    classes.append(mapped)

        return classes

    def _map_single_property(self, prop, value, prefix=''):
        """Map a single CSS property-value pair to Tailwind"""

        # Layout
        if prop == 'display':
            display_map = {
                'flex': 'flex', 'grid': 'grid', 'block': 'block',
                'inline': 'inline', 'inline-block': 'inline-block', 'none': 'hidden'
            }
            return f"{prefix}{display_map.get(value, '')}"

        # Flexbox
        elif prop == 'justify-content':
            justify_map = {
                'center': 'justify-center', 'space-between': 'justify-between',
                'flex-start': 'justify-start', 'flex-end': 'justify-end',
                'space-around': 'justify-around'
            }
            return f"{prefix}{justify_map.get(value, '')}"

        elif prop == 'align-items':
            align_map = {
                'center': 'items-center', 'flex-start': 'items-start',
                'flex-end': 'items-end', 'stretch': 'items-stretch'
            }
            return f"{prefix}{align_map.get(value, '')}"

        # Spacing - simplified
        elif prop in ['padding', 'margin']:
            return None  # Too complex for simple mapping

        # Colors
        elif prop in ['background-color', 'background']:
            if 'gradient' in value.lower():
                return None  # Complex gradient
            color = self._map_color_value(value)
            return f"{prefix}bg-{color}" if color else None

        elif prop == 'color':
            color = self._map_color_value(value)
            return f"{prefix}text-{color}" if color else None

        # Border
        elif prop == 'border-radius':
            radius_map = {
                '4px': 'rounded', '8px': 'rounded-lg', '0.5rem': 'rounded-lg',
                '12px': 'rounded-xl', '16px': 'rounded-2xl', '1rem': 'rounded-2xl',
                '50%': 'rounded-full', '9999px': 'rounded-full'
            }
            return f"{prefix}{radius_map.get(value, 'rounded')}"

        # Typography
        elif prop == 'font-weight':
            weight_map = {
                '400': 'font-normal', 'normal': 'font-normal',
                '500': 'font-medium', '600': 'font-semibold',
                '700': 'font-bold', 'bold': 'font-bold', '900': 'font-black'
            }
            return f"{prefix}{weight_map.get(value, '')}"

        elif prop == 'text-align':
            align_map = {
                'left': 'text-left', 'center': 'text-center',
                'right': 'text-right', 'justify': 'text-justify'
            }
            return f"{prefix}{align_map.get(value, '')}"

        # Position
        elif prop == 'position':
            pos_map = {
                'relative': 'relative', 'absolute': 'absolute',
                'fixed': 'fixed', 'sticky': 'sticky'
            }
            return f"{prefix}{pos_map.get(value, '')}"

        return None

    def _map_color_value(self, value):
        """Map color values to Tailwind tokens"""
        value = value.lower().strip()

        # Standard colors
        color_map = {
            '#ffffff': 'white', '#fff': 'white', 'white': 'white',
            '#000000': 'black', '#000': 'black', 'black': 'black',
            'transparent': 'transparent',
            '#f8f9fa': 'gray-100', '#e9ecef': 'gray-200',
            '#dee2e6': 'gray-300', '#6c757d': 'gray-500',
            '#495057': 'gray-600', '#343a40': 'gray-700',
            '#212529': 'gray-900'
        }

        if value in color_map:
            return color_map[value]

        # Check for rgb()
        if value.startswith('rgb'):
            return None  # Complex

        return None

    def _has_complex_properties(self, props):
        """Check if properties are complex (gradients, animations, etc.)"""
        complex_keywords = ['gradient', 'animation', 'transform', '@keyframes',
                           'transition', 'calc(', 'var(--']

        for prop, value in props.items():
            if any(kw in value.lower() for kw in complex_keywords):
                return True

            # Complex properties
            if prop in ['box-shadow', 'text-shadow', 'filter', 'backdrop-filter',
                       'clip-path', 'grid-template']:
                return True

        return False

    def save_mappings(self, output_file='css_tailwind_mappings.json'):
        """Save mappings to JSON"""
        output = {
            'total_mapped': len(self.mappings),
            'simple_count': sum(1 for m in self.mappings.values() if m.get('complexity') == 'simple'),
            'medium_count': sum(1 for m in self.mappings.values() if m.get('complexity') == 'medium'),
            'complex_count': sum(1 for m in self.mappings.values() if m.get('complexity') == 'high'),
            'mappings': self.mappings
        }

        Path(output_file).write_text(json.dumps(output, indent=2))
        print(f"\n{'='*60}")
        print(f"Mappings Summary:")
        print(f"  Simple: {output['simple_count']}")
        print(f"  Medium: {output['medium_count']}")
        print(f"  Complex: {output['complex_count']}")
        print(f"Saved to: {output_file}")
        print(f"{'='*60}")

if __name__ == '__main__':
    mapper = CSSTailwindMapper('legacy_css_definitions.json')
    mapper.map_all_classes()
    mapper.save_mappings()

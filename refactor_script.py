#!/usr/bin/env python3
"""
Refactoring script to split usif.py into modular structure
"""
import re
import os
from pathlib import Path

def extract_class_code(lines, start_line, end_line, imports_needed):
    """Extract class code and determine needed imports"""
    class_lines = lines[start_line:end_line]
    code = '\n'.join(class_lines)
    
    # Determine imports needed
    needed_imports = set()
    if 'struct' in code:
        needed_imports.add('import struct')
    if 'numpy' in code or 'np.' in code or 'np.ndarray' in code:
        needed_imports.add('import numpy as np')
    if 'hashlib' in code:
        needed_imports.add('import hashlib')
    if 'gzip' in code:
        needed_imports.add('import gzip')
    if 'Path' in code or 'pathlib' in code:
        needed_imports.add('from pathlib import Path')
    if 'MSONable' in code:
        needed_imports.add('from monty.json import MSONable')
    if 'TypeVar' in code or 'Generic' in code:
        needed_imports.add('from typing import TypeVar, Generic')
    if 'Optional' in code or 'Tuple' in code or 'List' in code or 'Dict' in code or 'Any' in code or 'Union' in code:
        needed_imports.add('from typing import Dict, List, Tuple, Optional, Union, Any')
    if 'dataclass' in code or '@dataclass' in code:
        needed_imports.add('from dataclasses import dataclass, field')
    if 'IntEnum' in code:
        needed_imports.add('from enum import IntEnum')
    if 'defaultdict' in code or 'OrderedDict' in code:
        needed_imports.add('from collections import defaultdict, OrderedDict')
    if 'queue' in code:
        needed_imports.add('import queue')
    if 'mmap' in code:
        needed_imports.add('import mmap')
    if 'threading' in code:
        needed_imports.add('import threading')
    if 'logging' in code:
        needed_imports.add('import logging')
    
    return code, needed_imports

def create_module_file(filepath, imports, code, header=""):
    """Create a module file with imports and code"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w') as f:
        f.write('#!/usr/bin/env python3\n')
        if header:
            f.write(f'"""{header}"""\n\n')
        f.write('\n'.join(sorted(imports)))
        f.write('\n\n')
        f.write(code)
        f.write('\n')

# Read original file
with open('usif.py', 'r') as f:
    lines = f.readlines()

# Extract header and imports from original file
header_lines = []
import_lines = []
in_imports = False
for i, line in enumerate(lines):
    if line.startswith('"""') or line.startswith("'''"):
        header_lines.append(line)
        if len(header_lines) == 1:
            in_imports = False
        elif len(header_lines) == 2:
            in_imports = True
    elif in_imports and (line.startswith('import ') or line.startswith('from ')):
        import_lines.append(line.rstrip())
    elif in_imports and line.strip() and not line.startswith('#'):
        in_imports = False

print("Extracted imports:")
for imp in import_lines:
    print(f"  {imp}")

# Now create the modular files
# This is a simplified version - we'll create key files manually for better control

print("\nRefactoring script ready. Key files will be created manually for better control.")


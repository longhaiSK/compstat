#!/bin/sh
""":"
exec "$(dirname "$0")/.venv/bin/python" "$0" "$@"
"""

import re
import sys
import os
import argparse

# ANSI Escape codes for bold text
BOLD = "\033[1m"
RESET = "\033[0m"

class Replacer:
    def __init__(self, replacement_template, content):
        self.replacement_template = replacement_template
        self.content = content
        self.replace_all = False
        self.count = 0
        self.ignored_matches = set()

    def get_truncated_display(self, text, length=150):
        if len(text) <= length:
            return text
        half = (length // 2) - 5
        return f"{text[:half]}\n[...] \n{text[-half:]}"

    def get_line_number(self, index):
        return self.content.count('\n', 0, index) + 1

    def replace_match(self, match):
        original_text = match.group(0)
        start_index = match.start()

        # Check if we've already ignored this specific string in this session
        if original_text in self.ignored_matches:
            return original_text

        # Process the template: 
        # 1. Manually handle literal '\n' and '\t' from the text file
        # 2. match.expand then resolves the '\1', '\2' backreferences
        template = self.replacement_template.replace(r"\n", "\n").replace(r"\t", "\t")
        
        try:
            new_text = match.expand(template)
        except Exception as e:
            print(f"Error expanding backreference: {e}")
            return original_text

        if self.replace_all:
            self.count += 1
            return new_text

        line_num = self.get_line_number(start_index)
        display_orig = self.get_truncated_display(original_text)
        display_new = self.get_truncated_display(new_text)

        print(f"\n{'='*70}")
        print(f"LINE {line_num} | MATCH FOUND:")
        print(f"{'-'*70}")
        print(display_orig)
        print(f"{'-'*30} PROPOSED REPLACEMENT {'-'*18}")
        print(display_new)
        print(f"{'='*70}")

        while True:
            choice = input("Replace? [y]es / [n]o / [a]ll / [v]iew full / [q]uit: ").lower().strip()
            if choice == 'y':
                self.count += 1
                return new_text
            elif choice == 'n':
                self.ignored_matches.add(original_text)
                return original_text
            elif choice == 'a':
                self.replace_all = True
                self.count += 1
                return new_text
            elif choice == 'v':
                print(f"\n--- FULL ORIGINAL ---\n{original_text}")
                print(f"\n--- FULL REPLACEMENT ---\n{new_text}\n")
                continue 
            elif choice == 'q':
                print("\nQuitting. No changes saved.")
                sys.exit(0)

def parse_patterns(pattern_file):
    tasks = []
    
    if not os.path.exists(pattern_file):
        print(f"Error: Pattern file '{pattern_file}' not found.")
        sys.exit(1)
    
    with open(pattern_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 1. Look for the start of a block (Title starting with #)
        if line.startswith("#"):
            # Check if we have enough lines left for a full block
            if i + 2 < len(lines):
                title = line.lstrip("#").strip()
                line_find = lines[i+1]
                line_repl = lines[i+2]
                
                # 2. Check strict structure: next line is 'find:', line after is 'repl:'
                # We check .strip() to ignore indentation, but ensure it doesn't start with # (commented out)
                s_find = line_find.strip()
                s_repl = line_repl.strip()
                
                if (s_find.lower().startswith("find:") and not s_find.startswith("#") and
                    s_repl.lower().startswith("repl:") and not s_repl.startswith("#")):
                    
                    # Extract the actual pattern content
                    # We strip newline/carriage return, then strip ONE leading space if present
                    current_find = line_find.split(":", 1)[1].strip('\n\r')
                    current_find = current_find.strip(' ')
                    
                    current_repl = line_repl.split(":", 1)[1].strip('\n\r')
                    current_repl = current_repl.strip(' ')
                    
                    tasks.append({
                        'title': title,
                        'find': current_find,
                        'repl': current_repl
                    })
                    
                    # Advance 3 lines since we consumed this block
                    i += 3
                    continue
        
        # If not a block start, or block was invalid/commented out, move to next line
        i += 1
        
    return tasks

def main():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    default_pattern_file = os.path.join(script_dir, "findreplpatterns.txt")

    parser = argparse.ArgumentParser(description="Regex Find/Replace (Python 're' flavor)")
    parser.add_argument("target", help="The file to modify")
    parser.add_argument("-p", "--patterns", default=default_pattern_file, 
                        help=f"Path to patterns file (default: {default_pattern_file})")
    args = parser.parse_args()

    tasks = parse_patterns(args.patterns)
    if not tasks:
        print(f"No valid pattern blocks found in {args.patterns}")
        print("Ensure format is 3 contiguous lines:\n# Title\nfind: pattern\nrepl: substitution")
        sys.exit(1)

    if not os.path.exists(args.target):
        print(f"Error: Target file '{args.target}' not found.")
        sys.exit(1)

    with open(args.target, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content
    total_modifications = 0
    master_ignored = set()

    for task in tasks:
        title = task['title']
        find_pat = task['find']
        repl_str = task['repl']

        # Print the Title in Bold
        print(f"\n{BOLD}>>> Rule: {title}{RESET}")

        replacer = Replacer(repl_str, new_content)
        replacer.ignored_matches = master_ignored
        try:
            new_content = re.sub(find_pat, replacer.replace_match, new_content, flags=re.M)
            total_modifications += replacer.count
            master_ignored = replacer.ignored_matches
        except re.error as e:
            print(f"Regex error in pattern '{find_pat}': {e}")

    if total_modifications > 0:
        with open(args.target + ".bak", 'w', encoding='utf-8') as f:
            f.write(content)
        with open(args.target, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"\nSuccess! Total modifications saved: {total_modifications}")
    else:
        print("\nNo changes made.")

if __name__ == "__main__":
    main()
    
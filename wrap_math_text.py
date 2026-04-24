#!/bin/sh
""":"
# 1. Try Unix venv
PYTHON_EXEC="$(dirname "$0")/.venv/bin/python"

# 2. If not found, try Windows venv
if [ ! -f "$PYTHON_EXEC" ]; then
    PYTHON_EXEC="$(dirname "$0")/.venv/Scripts/python"
fi

# 3. If still not found, try system PATH
if [ ! -f "$PYTHON_EXEC" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_EXEC="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_EXEC="python"
    else
        echo "rit: Neither virtualenv nor system Python found." >&2
        exit 1
    fi
fi

exec "$PYTHON_EXEC" "$0" "$@"
"""

import re
import sys
import os
import json

# --- DEFAULTS ---
CONFIG_FILE = ".math_wrap_config.json"

DEFAULT_INCLUSIONS = {
    'MSE', 'SSR', 'SSE', 'SSH', 'SST', 'MSA', 'MSB', 'MSC', 'MLE', 'OLS', 'GLS', 
    'WLS', 'BLUE', 'PDF', 'CDF', 'PMF', 'MGF', 'AIC', 'BIC', 'DIC', 'VIF', 
    'IID', 'RNG', 'SD', 'SE', 'CV', 'ANOVA', 'MANOVA', 'ANCOVA', 'LRT', 
    'GLM', 'GAM', 'ROC', 'AUC'
}

DEFAULT_BLACKLIST = {'PI', 'LN', 'EXP', 'SIN', 'COS', 'TAN', 'DET', 'VAR', 'COV', 'COR', 'PR'}
DEFAULT_TEXT_CMDS = {'text', 'mathrm', 'mathbf', 'textit', 'textbf', 'sf', 'mbox'}

class PersistentReplacer:
    def __init__(self):
        self.load_config()
        self.interactive = True
        self.count = 0

    def load_config(self):
        """Loads lists from hidden file or initializes them with defaults."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.inclusions = set(data.get('inclusions', DEFAULT_INCLUSIONS))
                    self.blacklist = set(data.get('blacklist', DEFAULT_BLACKLIST))
                    self.text_commands = set(data.get('text_commands', DEFAULT_TEXT_CMDS))
                print(f"[*] Loaded configuration from {CONFIG_FILE}")
            except Exception as e:
                print(f"[!] Error loading config: {e}. Using defaults.")
                self.init_defaults()
        else:
            self.init_defaults()

    def init_defaults(self):
        self.inclusions = set(DEFAULT_INCLUSIONS)
        self.blacklist = set(DEFAULT_BLACKLIST)
        self.text_commands = set(DEFAULT_TEXT_CMDS)

    def save_config(self):
        """Writes current state back to the hidden file."""
        data = {
            'inclusions': sorted(list(self.inclusions)),
            'blacklist': sorted(list(self.blacklist)),
            'text_commands': sorted(list(self.text_commands))
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"[*] Configuration saved to {CONFIG_FILE}")

    def process_match(self, match):
        if match.group(1): return match.group(1) # Skip code
        
        delimiter = match.group(2) or match.group(4)
        content = match.group(3) or match.group(5)
        
        # Regex for 2+ uppercase letters
        acronym_pattern = r'(?<!\\)\b([A-Z]{2,})\b'
        
        def word_sub(m):
            word = m.group(1)
            
            if word in self.blacklist: return word
            if is_already_wrapped(content, m.start(1), self.text_commands): return word
            if word in self.inclusions:
                self.count += 1
                return f"\\text{{{word}}}"

            if not self.interactive: return word

            print(f"\n{'-'*30}")
            snippet = content[max(0, m.start()-20):min(len(content), m.end()+20)].replace('\n', ' ')
            print(f"CONTEXT: {delimiter} ...{snippet}... {delimiter}")
            
            while True:
                choice = input(f"Wrap '{word}'? [y]es / [n]o / [a]ll yes / [q]uit: ").lower().strip()
                if choice == 'y':
                    self.inclusions.add(word)
                    self.count += 1
                    return f"\\text{{{word}}}"
                elif choice == 'n':
                    self.blacklist.add(word)
                    return word
                elif choice == 'a':
                    self.interactive = False
                    self.inclusions.add(word)
                    self.count += 1
                    return f"\\text{{{word}}}"
                elif choice == 'q':
                    self.save_config()
                    sys.exit(0)

        new_content = re.sub(acronym_pattern, word_sub, content)
        return delimiter + new_content + delimiter

def is_already_wrapped(full_string, start_index, text_commands):
    balance = 0
    for i in range(start_index - 1, -1, -1):
        if full_string[i] == '}': balance += 1
        elif full_string[i] == '{':
            if balance > 0: balance -= 1
            else:
                match = re.search(r'\\([a-z]+)\s*$', full_string[:i])
                if match and match.group(1) in text_commands:
                    return True
                return False 
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <filename.qmd>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    with open(file_path, 'r', encoding='utf-8') as f:
        full_content = f.read()

    # Create backup
    with open(file_path + ".bak", 'w', encoding='utf-8') as f:
        f.write(full_content)

    master_pattern = r'(?s)(`{1,3}.+?`{1,3})|(?<!\\)(\$\$)(.+?)(?<!\\)\$\$|(?<!\\)(\$)([^$\n`]+?)(?<!\\)\$'
    
    replacer = PersistentReplacer()
    new_content = re.sub(master_pattern, replacer.process_match, full_content)

    if replacer.count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"\nFinished! Wrapped {replacer.count} terms.")
    else:
        print("\nNo changes made.")
    
    replacer.save_config()

if __name__ == "__main__":
    main()
    
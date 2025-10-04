#!/usr/bin/env python3
import shutil
import os
import sys

def copytree(src, dst, ignore=None):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore)


def main(out_dir="sell_manager_CLI_clean"):
    root = os.getcwd()
    out_path = os.path.abspath(out_dir)
    print(f"Creating cleaned copy at {out_path}")

    copytree(root, out_path, ignore=shutil.ignore_patterns('.git', 'logs', 'config/cache', '__pycache__'))

    # Remove assigned_ma if present and add example
    cfg_dir = os.path.join(out_path, 'config')
    os.makedirs(cfg_dir, exist_ok=True)
    assigned = os.path.join(cfg_dir, 'assigned_ma.example.csv')
    with open(assigned, 'w') as f:
        f.write('# ticker,ma_period,assigned_to\nEXAMPLE,20,example_user\n')

    # Ensure .gitignore and LICENSE included
    gi = os.path.join(out_path, '.gitignore')
    with open(gi, 'w') as f:
        f.write('logs/\nconfig/cache/\n__pycache__/\n.venv/\n.vscode/\n.idea/\n*.pyc\n')

    lic = os.path.join(out_path, 'LICENSE')
    if not os.path.exists(lic):
        with open(lic, 'w') as f:
            f.write('MIT License\n\nCopyright (c) 2025\n')

    print('Clean export ready')

if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else 'sell_manager_CLI_clean'
    main(arg)

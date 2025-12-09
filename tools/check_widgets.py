from pathlib import Path

def main():
    p = Path("src/sellmanagement/gui/widgets.py")
    text = p.read_bytes().decode('utf-8', errors='replace')
    lines = text.splitlines()
    stack = []
    for i, l in enumerate(lines, start=1):
        s = l.lstrip()
        if s.startswith("try:"):
            stack.append(i)
            print(f"{i:4d}: try -> push {i} (depth {len(stack)})")
        if s.startswith("except ") or s.startswith("except:") or s.startswith("finally:"):
            if stack:
                popped = stack.pop()
                print(f"{i:4d}: except/finally -> pop {popped} (depth {len(stack)})")
            else:
                print("Unmatched except at", i)
    print("unmatched try lines after parsing:", stack)
    # print context around suspected error
    err_line = 687
    start = max(1, err_line - 10)
    for i in range(start, err_line + 5):
        print(f"{i:4d}: {lines[i-1]}")

if __name__ == '__main__':
    main()



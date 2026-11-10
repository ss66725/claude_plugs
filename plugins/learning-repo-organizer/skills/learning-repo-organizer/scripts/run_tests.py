"""Run the sample-input tests stored in every tests/ folder of this repository.

Each test file  <folder>/tests/<name>.txt  belongs to the program
<folder>/<name>.c  (or .py). A test file holds one or more cases:

    input:
    3 9 5
    output:
    The largest number is 9
    ---
    input:
    1 2 3
    output:
    The largest number is 3

Usage:
    python run_tests.py              run every test
    python run_tests.py 261023       run only tests under a folder
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))


def parse_cases(text):
    cases, current, section = [], None, None
    for line in text.splitlines():
        if line == "input:":
            if current is not None:
                cases.append(current)
            current, section = {"input": [], "output": []}, "input"
        elif line == "output:":
            section = "output"
        elif line == "---":
            section = None
        elif current is not None and section is not None:
            current[section].append(line)
    if current is not None:
        cases.append(current)
    return cases


def normalize(text):
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def find_tests(path_filter):
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        if os.path.basename(dirpath) != "tests":
            continue
        parent = os.path.dirname(dirpath)
        for filename in sorted(filenames):
            if not filename.endswith(".txt"):
                continue
            stem = filename[:-4]
            source = None
            for ext in (".c", ".py"):
                candidate = os.path.join(parent, stem + ext)
                if os.path.exists(candidate):
                    source = candidate
                    break
            rel = os.path.relpath(os.path.join(dirpath, filename), ROOT).replace("\\", "/")
            if path_filter and not rel.startswith(path_filter):
                continue
            found.append((rel, os.path.join(dirpath, filename), source))
    return sorted(found)


def build_command(source, workdir):
    if source.endswith(".py"):
        return [sys.executable, source]
    exe = os.path.join(workdir, os.path.splitext(os.path.basename(source))[0] + ".exe")
    result = subprocess.run(
        ["gcc", "-std=c11", "-Wall", "-Wextra", "-o", exe, source, "-lm"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("compile failed:\n" + result.stderr)
    return [exe]


def main():
    path_filter = sys.argv[1].replace("\\", "/") if len(sys.argv) > 1 else ""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONHASHSEED="0")  # fixed set order
    passed = failed = 0
    with tempfile.TemporaryDirectory() as workdir:
        for rel, test_file, source in find_tests(path_filter):
            if source is None:
                print(f"SKIP  {rel}  (no matching program)")
                continue
            with open(test_file, encoding="utf-8") as f:
                cases = parse_cases(f.read())
            try:
                command = build_command(source, workdir)
            except RuntimeError as error:
                print(f"FAIL  {rel}  {error}")
                failed += len(cases)
                continue
            for index, case in enumerate(cases, 1):
                stdin_text = "\n".join(case["input"]) + "\n" if case["input"] else ""
                try:
                    run = subprocess.run(command, input=stdin_text.encode("utf-8"),
                                         capture_output=True, timeout=10, env=env)
                    actual = run.stdout.decode("utf-8", errors="replace")
                except subprocess.TimeoutExpired:
                    actual = "<timeout>"
                expected = "\n".join(case["output"])
                if normalize(actual) == normalize(expected):
                    passed += 1
                    print(f"PASS  {rel}  case {index}")
                else:
                    failed += 1
                    print(f"FAIL  {rel}  case {index}")
                    print("      expected: " + normalize(expected).replace("\n", "\n"))
                    print("      actual:   " + normalize(actual).replace("\n", "\n"))
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

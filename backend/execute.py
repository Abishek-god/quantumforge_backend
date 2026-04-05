"""
Quantum Forge — Code Execution Engine
Sandboxed Python code runner with test case validation.
"""

import subprocess
import tempfile
import os
import time
import re

# Imports that are blocked for security
BLOCKED_IMPORTS = [
    "os", "sys", "subprocess", "shutil", "importlib",
    "ctypes", "socket", "http", "urllib", "requests",
    "pathlib", "glob", "signal", "threading", "multiprocessing",
    "pickle", "shelve", "marshal", "code", "codeop",
    "compile", "compileall", "exec", "eval",
    "__import__", "open",
]

TIMEOUT_SECONDS = 5
MAX_OUTPUT_LENGTH = 5000


def check_dangerous_code(code):
    """Check for potentially dangerous code patterns."""
    dangers = []

    for imp in BLOCKED_IMPORTS:
        patterns = [
            rf'\bimport\s+{imp}\b',
            rf'\bfrom\s+{imp}\b',
            rf'__import__\s*\(\s*["\']?{imp}',
        ]
        for pattern in patterns:
            if re.search(pattern, code):
                dangers.append(f"Blocked import: '{imp}' is not allowed for security.")

    # Check for file operations
    if re.search(r'\bopen\s*\(', code):
        dangers.append("File operations are not allowed.")

    # Check for exec/eval
    if re.search(r'\b(exec|eval)\s*\(', code):
        dangers.append("exec() and eval() are not allowed.")

    return dangers


def execute_code(code, timeout=TIMEOUT_SECONDS):
    """
    Execute Python code in a subprocess and capture output.
    Returns dict with: output, error, execution_time, success
    """
    # Security check
    dangers = check_dangerous_code(code)
    if dangers:
        return {
            "output": "",
            "error": "\n".join(dangers),
            "execution_time": 0,
            "success": False,
        }

    # Write code to temp file
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_path = f.name
    except Exception as e:
        return {
            "output": "",
            "error": f"Failed to create temp file: {str(e)}",
            "execution_time": 0,
            "success": False,
        }

    try:
        start_time = time.time()
        result = subprocess.run(
            ["python", temp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
        )
        execution_time = round(time.time() - start_time, 3)

        output = result.stdout[:MAX_OUTPUT_LENGTH]
        error = result.stderr[:MAX_OUTPUT_LENGTH]

        return {
            "output": output,
            "error": error,
            "execution_time": execution_time,
            "success": result.returncode == 0,
        }

    except subprocess.TimeoutExpired:
        return {
            "output": "",
            "error": f"⏱️ Time Limit Exceeded! Your code took longer than {timeout} seconds.",
            "execution_time": timeout,
            "success": False,
        }
    except Exception as e:
        return {
            "output": "",
            "error": f"Execution error: {str(e)}",
            "execution_time": 0,
            "success": False,
        }
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def run_test_cases(code, test_cases, function_name=None):
    """
    Run code against a list of test cases.
    Each test case: { "input": "...", "expected": "..." }
    Returns: { passed: bool, results: [...], total: int, passed_count: int }
    """
    results = []
    passed_count = 0

    for i, test in enumerate(test_cases):
        test_input = test.get("input", "")
        expected = str(test.get("expected", "")).strip()

        # Build test wrapper
        if function_name:
            # Call the function and print the result
            test_code = f"""{code}

# ── Test Runner ──
_result = {function_name}({test_input})
print(repr(_result) if isinstance(_result, str) else _result)
"""
        else:
            test_code = code

        result = execute_code(test_code)

        actual_output = result["output"].strip()

        # Compare output
        test_passed = actual_output == expected

        results.append({
            "test_number": i + 1,
            "input": test_input,
            "expected": expected,
            "actual": actual_output,
            "passed": test_passed,
            "error": result["error"],
            "execution_time": result["execution_time"],
        })

        if test_passed:
            passed_count += 1

    return {
        "passed": passed_count == len(test_cases),
        "results": results,
        "total": len(test_cases),
        "passed_count": passed_count,
    }


def extract_function_name(code):
    """Extract the main function name from user code."""
    match = re.search(r'def\s+(\w+)\s*\(', code)
    return match.group(1) if match else None

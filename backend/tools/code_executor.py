import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

MAX_CODE_CHARS = 50000
MAX_OUTPUT_CHARS = 12000
MAX_TIMEOUT_SECONDS = 15

ALIASES = {
    "py": "python",
    "python3": "python",
    "js": "javascript",
    "node": "javascript",
    "ts": "typescript",
    "c++": "cpp",
    "golang": "go",
    "rs": "rust",
}


def clip(text):
    text = text or ""
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + "\n...[truncated]"
    return text


def run_process(command, cwd, timeout):
    """Run a process with a bounded timeout and captured output.

    Important: this is not a security sandbox. Do not run untrusted code
    without operating-system-level isolation and resource restrictions.
    """
    started = time.monotonic()

    # Use a minimal environment rather than copying API keys and other secrets
    # from the parent process into the code execution environment.
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "WINDIR": os.environ.get("WINDIR", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    env = {key: value for key, value in env.items() if value}

    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(max(int(timeout), 1), MAX_TIMEOUT_SECONDS),
            shell=False,
        )
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": clip(result.stdout),
            "stderr": clip(result.stderr),
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "return_code": None,
            "stdout": "",
            "stderr": "",
            "error": f"Execution timed out after {timeout} seconds.",
        }
    except OSError as exc:
        return {
            "success": False,
            "return_code": None,
            "stdout": "",
            "stderr": "",
            "error": str(exc),
        }


def execute_code(language: str, code: str, timeout_seconds: int = 8):
    """Execute code with an installed local runtime.

    WARNING: This runner is not a secure sandbox. Running arbitrary code can
    access files and resources available to the current Windows user. Only use
    it for trusted code until OS-level isolation is implemented.
    """
    if not isinstance(language, str):
        return {
            "tool": "code_execution",
            "success": False,
            "language": "",
            "error": "Language must be a string.",
        }

    language = ALIASES.get(language.strip().lower(), language.strip().lower())

    if not isinstance(code, str) or not code.strip():
        return {
            "tool": "code_execution",
            "success": False,
            "language": language,
            "error": "No code provided.",
        }

    if len(code) > MAX_CODE_CHARS:
        return {
            "tool": "code_execution",
            "success": False,
            "language": language,
            "error": "Code is too large.",
        }

    try:
        timeout = min(max(int(timeout_seconds), 1), MAX_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        timeout = 8

    if language == "sql":
        try:
            with sqlite3.connect(":memory:") as connection:
                cursor = connection.cursor()
                statements = [statement.strip() for statement in code.split(";")
                              if statement.strip()]
                output = []

                for statement in statements:
                    cursor.execute(statement)
                    if cursor.description:
                        output.append({
                            "columns": [column[0] for column in cursor.description],
                            "rows": cursor.fetchmany(200),
                        })

                return {
                    "tool": "code_execution",
                    "success": True,
                    "language": language,
                    "phase": "run",
                    "stdout": repr(output),
                    "stderr": "",
                    "return_code": 0,
                }
        except sqlite3.Error as exc:
            return {
                "tool": "code_execution",
                "success": False,
                "language": language,
                "phase": "run",
                "error": str(exc),
            }

    runtimes = {
        "python": ("python", "main.py"),
        "javascript": ("node", "main.js"),
        "typescript": ("npx", "main.ts"),
        "java": ("javac", "Main.java"),
        "c": ("gcc", "main.c"),
        "cpp": ("g++", "main.cpp"),
        "php": ("php", "main.php"),
        "go": ("go", "main.go"),
        "rust": ("rustc", "main.rs"),
    }

    if language not in runtimes:
        return {
            "tool": "code_execution",
            "success": False,
            "language": language,
            "error": "Unsupported language.",
        }

    runtime, filename = runtimes[language]
    runtime_path = shutil.which(runtime)
    if not runtime_path:
        return {
            "tool": "code_execution",
            "success": False,
            "language": language,
            "error": f"Required runtime '{runtime}' is not installed or not on PATH.",
        }

    try:
        with tempfile.TemporaryDirectory(prefix="nova_code_") as temp:
            workdir = Path(temp)
            source = workdir / filename
            source.write_text(code, encoding="utf-8")
            binary = workdir / ("program.exe" if os.name == "nt" else "program")

            if language == "python":
                command = [runtime_path, "-I", str(source)]
            elif language == "javascript":
                command = [runtime_path, str(source)]
            elif language == "typescript":
                # npx may download packages when run. Only use with trusted code.
                command = [runtime_path, "--yes", "tsx", str(source)]
            elif language == "php":
                command = [runtime_path, str(source)]
            elif language == "go":
                command = [runtime_path, "run", str(source)]
            elif language == "java":
                compiled = run_process([runtime_path, str(source)], workdir, timeout)
                if not compiled["success"]:
                    return {
                        "tool": "code_execution",
                        "language": language,
                        "phase": "compile",
                        **compiled,
                    }
                java_path = shutil.which("java")
                if not java_path:
                    return {
                        "tool": "code_execution",
                        "success": False,
                        "language": language,
                        "phase": "run",
                        "error": "Required runtime 'java' is not installed or not on PATH.",
                    }
                command = [java_path, "-cp", str(workdir), "Main"]
            elif language in ("c", "cpp", "rust"):
                if language == "rust":
                    compile_command = [runtime_path, str(source), "-o", str(binary)]
                elif language == "c":
                    compile_command = [runtime_path, str(source), "-o", str(binary)]
                else:
                    compile_command = [
                        runtime_path, "-std=c++17", str(source), "-o", str(binary)
                    ]

                compiled = run_process(compile_command, workdir, timeout)
                if not compiled["success"]:
                    return {
                        "tool": "code_execution",
                        "language": language,
                        "phase": "compile",
                        **compiled,
                    }
                command = [str(binary)]
            else:
                return {
                    "tool": "code_execution",
                    "success": False,
                    "language": language,
                    "error": "Unsupported language.",
                }

            result = run_process(command, workdir, timeout)
            return {
                "tool": "code_execution",
                "language": language,
                "phase": "run",
                **result,
            }
    except Exception as exc:
        return {
            "tool": "code_execution",
            "success": False,
            "language": language,
            "error": str(exc),
        }

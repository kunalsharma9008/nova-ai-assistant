
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

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
    env = os.environ.copy()
    started = time.monotonic()

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

    This runner is NOT a secure sandbox. Do not use for
    untrusted code without OS-level isolation.
    """
    language = ALIASES.get(language.strip().lower(), language.strip().lower())

    if not isinstance(code, str) or not code.strip():
        return {"success": False, "language": language, "error": "No code provided."}

    if len(code) > MAX_CODE_CHARS:
        return {"success": False, "language": language, "error": "Code is too large."}

    if language == "sql":
        try:
            with sqlite3.connect(":memory:") as connection:
                cursor = connection.cursor()
                statements = [s.strip() for s in code.split(";") if s.strip()]
                output = []

                for statement in statements:
                    cursor.execute(statement)
                    if cursor.description:
                        output.append({
                            "columns": [col[0] for col in cursor.description],
                            "rows": cursor.fetchmany(200),
                        })

                return {
                    "tool": "code_execution",
                    "success": True,
                    "language": language,
                    "stdout": repr(output),
                    "stderr": "",
                }

        except sqlite3.Error as exc:
            return {
                "tool": "code_execution",
                "success": False,
                "language": language,
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
    if not shutil.which(runtime):
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

            timeout = min(max(int(timeout_seconds), 1), MAX_TIMEOUT_SECONDS)
            binary = workdir / ("program.exe" if os.name == "nt" else "program")

            if language == "python":
                command = [shutil.which("python"), "-I", str(source)]

            elif language == "javascript":
                command = [shutil.which("node"), str(source)]

            elif language == "typescript":
                command = [shutil.which("npx"), "--yes", "tsx", str(source)]

            elif language == "php":
                command = [shutil.which("php"), str(source)]

            elif language == "go":
                command = [shutil.which("go"), "run", str(source)]

            elif language == "java":
                compiled = run_process(
                    [shutil.which("javac"), str(source)],
                    workdir,
                    timeout,
                )
                if not compiled["success"]:
                    return {
                        "tool": "code_execution",
                        "language": language,
                        "phase": "compile",
                        **compiled,
                    }
                command = [
                    shutil.which("java"),
                    "-cp", str(workdir), "Main",
                ]

            elif language in ("c", "cpp", "rust"):
                compiler = shutil.which(runtime)

                if language == "rust":
                    compile_command = [compiler, str(source), "-o", str(binary)]
                elif language == "c":
                    compile_command = [compiler, str(source), "-o", str(binary)]
                else:
                    compile_command = [
                        compiler, "-std=c++17", str(source), "-o", str(binary)
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

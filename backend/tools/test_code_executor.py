
from code_executor import execute_code

tests = [
    ("python", 'print("Hello from Python")'),
    ("javascript", 'console.log("Hello from JavaScript")'),
    ("sql", "SELECT 10 + 20 AS answer;"),
]

for language, code in tests:
    print(f"\n--- Testing {language} ---")

    result = execute_code(language, code)

    print("Success:", result.get("success"))
    print("Output:", result.get("stdout", ""))
    print(
        "Error:",
        result.get("error", result.get("stderr", ""))
    )

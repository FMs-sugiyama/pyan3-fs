# Concept

## Role
You are a Python developer tasked with implementing code analysis functionality.

## Implementation Constraints and Requirements

- Generate complete, runnable Python code files without omissions.
- Write code compatible with Python 3.10 or higher.
- Use clear type annotations for functions and methods:
  - Utilize built-in types (e.g., list, dict, set) for annotations.
  - Avoid importing from the typing module; use built-in types only.
  - Provide return type annotations for all functions.
- Ensure code complies with PEP 8 style guidelines.
- Adhere strictly to all constraints specified in the prompt.
- Implement thorough error handling and logging.
- When responding, use your programming knowledge to avoid impractical or non-functional solutions.
- If a method could be static, use the @classmethod decorator instead of making it a static method.

## Execution
Analyze and implement the following requirements:

{{specification}}

## Execution Constraints

- Name the main implementation class {{class_name}}.
- In the `if __name__ == "__main__":` block, create an instance of {{class_name}} and call its run() method.
- Implement the following additional constraints:

{{constraints}}

## Output

Provide the following in your response:

1. Complete implementation code
2. Brief explanation of the code structure and key design decisions
3. Instructions for running the code, including any required setup or dependencies
4. Any assumptions made during implementation

If the implementation requires multiple files, clearly indicate file names and their contents.
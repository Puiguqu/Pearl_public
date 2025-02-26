import os
import re
import ast
import asyncio
import subprocess
import shutil
from pathlib import Path
import ollama
import aiofiles
import importlib.util
import inspect
import random
import string

# Dummy Telegram client for installation messages
class DummyTelegramClient:
    async def send_message(self, chat_id: int, message: str):
        print(f"Telegram message to {chat_id}: {message}")

def extract_missing_module(error_message: str) -> str:
    """
    Extracts the missing module name from an ImportError message.
    For example, from "No module named 'requests'" it returns "requests".
    """
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_message)
    if match:
        return match.group(1)
    return ""

def extract_async_function(raw_output: str) -> str:
    """
    Extract only the code from the first 'async def ...' line
    through the end of that function block, discarding any extra text.
    """
    lines = raw_output.splitlines()
    start_index = None
    extracted_lines = []

    for i, line in enumerate(lines):
        if line.strip().startswith("async def "):
            start_index = i
            break

    if start_index is None:
        return ""

    extracted_lines.append(lines[start_index])
    base_indent = len(lines[start_index]) - len(lines[start_index].lstrip())

    for line in lines[start_index + 1:]:
        stripped_line = line.lstrip()
        current_indent = len(line) - len(line.lstrip())
        if (stripped_line.startswith("async def ") or stripped_line.startswith("def ")) and current_indent <= base_indent:
            break
        extracted_lines.append(line)

    return "\n".join(extracted_lines).strip()

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import the install_package function from core.package_installer
from core.package_installer import install_package

class PearlSelfEditor:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        self.llm = ollama
        self.backup_path = self.repo_path / "backup"
        self.modules_path = self.repo_path / "modules"
        self.core_path = self.repo_path / "core"
        self.backup_path.mkdir(exist_ok=True)

    async def find_all_python_files(self):
        file_paths = []
        if self.modules_path.is_dir():
            file_paths += [str(f.relative_to(self.repo_path)) for f in self.modules_path.rglob("*.py")]
        if self.core_path.is_dir():
            file_paths += [str(f.relative_to(self.repo_path)) for f in self.core_path.rglob("*.py")]
        return file_paths

    async def backup_file(self, file_path: str):
        src = self.repo_path / file_path
        dest = self.backup_path / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dest)

    async def load_code(self, file_path: str) -> str:
        abs_path = self.repo_path / file_path
        if not abs_path.exists():
            return ""
        async with aiofiles.open(abs_path, "r", encoding="utf-8") as f:
            return await f.read()

    def strip_triple_backticks(self, text: str) -> str:
        text = re.sub(r"```+(\w+)?", "", text)
        text = re.sub(r"```", "", text)
        return text

    def parse_first_function_name(self, code: str) -> str:
        match = re.search(r"async\s+def\s+([a-zA-Z_]\w*)\s*\(", code)
        if match:
            return match.group(1)
        return ""

    def validate_syntax_or_none(self, code: str) -> str:
        try:
            ast.parse(code)
        except SyntaxError as e:
            return str(e)
        return None

    async def re_prompt_for_syntax_errors(self, original_code: str, syntax_err_msg: str) -> str:
        fix_prompt = (
            "You have produced Python code with a syntax error.\n\n"
            f"Syntax error message:\n{syntax_err_msg}\n\n"
            "Current code:\n"
            f"{original_code}\n\n"
            "You MUST return only a valid async function, with no extra text or docstrings.\n"
            "No lines before 'async def ...' are allowed.\n"
            "Please fix this and return only the valid function code.\n"
            "You may import any packages you deem necessary."
        )
        client = self.llm.Client()
        response = client.generate(model="codellama:13b", prompt=fix_prompt)
        new_code = response.get("response", "")
        print("DEBUG: LLM output (re_prompt_for_syntax_errors):", new_code)
        new_code = extract_async_function(new_code)
        return self.strip_triple_backticks(new_code)

    async def test_function(self, file_path: str, function_name: str = "function_to_test") -> bool:
        """
        Inspects the function signature and generates random appropriate arguments.
        If an ImportError is raised, attempts to install the missing package.
        """
        try:
            module_path = self.repo_path / file_path
            spec = importlib.util.spec_from_file_location("modified_module", str(module_path))
            if not spec or not spec.loader:
                print("Failed to create module spec.")
                return False
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, function_name):
                func = getattr(module, function_name)
                sig = inspect.signature(func)

                def generate_random_value(param):
                    if param.annotation == int:
                        return random.randint(1, 100)
                    elif param.annotation == float:
                        return random.uniform(1.0, 100.0)
                    elif param.annotation == str:
                        return ''.join(random.choices(string.ascii_letters, k=8))
                    elif param.annotation == bool:
                        return random.choice([True, False])
                    elif param.annotation == list:
                        return [random.randint(1, 100) for _ in range(random.randint(1, 5))]
                    elif param.annotation == dict:
                        return {f"key{random.randint(1, 10)}": random.randint(1, 100)}
                    elif param.annotation == set:
                        return {random.randint(1, 100) for _ in range(random.randint(1, 5))}
                    elif param.annotation == tuple:
                        return (random.randint(1, 100), random.randint(1, 100))
                    else:
                        return random.randint(1, 100)

                params = {}
                for param_name, param in sig.parameters.items():
                    if param.default == inspect._empty:
                        params[param_name] = generate_random_value(param)

                print(f"Generated test arguments for {function_name}: {params}")
                if asyncio.iscoroutinefunction(func):
                    result = await func(**params)
                else:
                    result = func(**params)
                print(f"{function_name} returned:", result)
            else:
                print(f"File '{file_path}' does not define {function_name}.")
            return True

        except ImportError as e:
            error_message = str(e)
            missing_module = extract_missing_module(error_message)
            if missing_module:
                print(f"Missing module detected: {missing_module}. Attempting installation...")
                # Use a dummy TelegramClient and chat_id=0
                dummy_client = DummyTelegramClient()
                await install_package(missing_module, 0, dummy_client)
                # After installation, try re-importing and re-running the function
                return await self.test_function(file_path, function_name)
            else:
                print(f"ImportError occurred: {error_message}")
                return False

        except Exception as e:
            print(f"Function test failed ({function_name}): {e}")
            return False

    async def run_tests(self) -> bool:
        try:
            process = await asyncio.create_subprocess_exec(
                "python", "-m", "unittest", "discover",
                "-s", str(self.repo_path),
                "-p", "test_*.py",
                cwd=str(self.repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            print("Test Output:")
            if stdout:
                print(stdout.decode())
            if not stdout and not stderr:
                print("No tests found. Running scripts manually...")
                test_files = list(self.repo_path.rglob("test_*.py"))
                for test_file in test_files:
                    print("Running", test_file, "...")
                    subprocess.run(["python", str(test_file)], cwd=self.repo_path)
            print("Test Errors:")
            if stderr:
                print(stderr.decode())
            return process.returncode == 0
        except Exception as e:
            print(f"Test execution failed: {e}")
            return False

    async def commit_changes(self, file_path: str):
        try:
            subprocess.run(["git", "add", file_path], cwd=self.repo_path, check=True)
            subprocess.run(["git", "commit", "-m", f"Automated edit to {file_path}"], cwd=self.repo_path, check=True)
            subprocess.run(["git", "push"], cwd=self.repo_path, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Git operation failed: {e}")

    async def revert_changes(self, file_path: str):
        src = self.backup_path / file_path
        dest = self.repo_path / file_path
        if src.exists():
            shutil.copy2(src, dest)
            print(f"Changes reverted for {file_path}.")
        else:
            if dest.exists():
                os.remove(dest)
            print(f"No backup found for {file_path}, file removed.")

    async def locate_file_for_function(self, python_files, function_name: str) -> str:
        found_in = []
        for file_path in python_files:
            code = await self.load_code(file_path)
            if f"async def {function_name}(" in code:
                found_in.append(file_path)
        if len(found_in) == 1:
            return found_in[0]
        return ""

    async def create_new_file(self, file_basename: str) -> str:
        new_file_name = file_basename if file_basename.endswith(".py") else f"{file_basename}.py"
        new_file_path = self.modules_path / new_file_name
        new_file_path.parent.mkdir(parents=True, exist_ok=True)
        if not new_file_path.exists():
            new_file_path.touch()
        return str(new_file_path.relative_to(self.repo_path))

    async def apply_edit(self, file_path: str, new_code: str):
        abs_path = self.repo_path / file_path
        async with aiofiles.open(abs_path, "w", encoding="utf-8") as f:
            await f.write(new_code)

    async def ask_llm_for_code_when_no_function_name(self, modification_request: str) -> str:
        """
        Called when no function name is provided.
        No reference code is sent.
        """
        prompt = (
            "You are an AI assistant that must produce only valid Python code for exactly one async function.\n"
            "You may import any packages you deem necessary.\n"
            "No docstrings or repeated lines are allowed. No lines before 'async def ...' are allowed.\n"
            "You must define a brand-new function name, starting with 'async def' and ending at the final line of the function.\n"
            "Do NOT return any non-async functions. Every function must be written using 'async def'.\n"
            "No extra text, commentary, or file headers are allowed.\n\n"
            f"Modification Request:\n{modification_request}\n\n"
            "Return only the function code with no extra text."
        )
        client = self.llm.Client()
        response = client.generate(model="codellama:13b", prompt=prompt)
        raw_code = response.get("response", "")
        print("DEBUG: LLM output (ask_llm_for_code_when_no_function_name):", raw_code)

        extracted = extract_async_function(raw_code)
        extracted = self.strip_triple_backticks(extracted)
        if extracted.startswith("def "):
            print("Detected non-async function, converting to async...")
            extracted = extracted.replace("def ", "async def ", 1)
        return extracted

    async def finalize_code_with_retries(self, code: str) -> str:
        attempts = 0
        while attempts < 3:
            syntax_err = self.validate_syntax_or_none(code)
            if syntax_err is None:
                return code
            print(f"Syntax error detected (attempt {attempts + 1}):", syntax_err)
            code = await self.re_prompt_for_syntax_errors(code, syntax_err)
            attempts += 1

        print("Three attempts failed, trying a different approach.")
        alt_prompt = (
            "You must provide only a valid async function definition, with no extra text or docstrings.\n"
            "Start your output with 'async def' and end at the last line of the function.\n"
            "You may import any packages you deem necessary.\n"
            "Nothing else is allowed."
        )
        client = self.llm.Client()
        response = client.generate(model="codellama:13b", prompt=alt_prompt)
        new_code = response.get("response", "")
        print("DEBUG: LLM output (alternative approach):", new_code)
        new_code = extract_async_function(new_code)
        new_code = self.strip_triple_backticks(new_code)
        syntax_err = self.validate_syntax_or_none(new_code)
        if syntax_err is None:
            return new_code
        else:
            print("Alternative approach still invalid:", syntax_err)
            return ""

    async def modify_single_file(self, file_path: str, modification_request: str, function_name: str, is_new_file: bool):
        await self.backup_file(file_path)
        current_code = ""
        if not is_new_file:
            current_code = await self.load_code(file_path)

        if is_new_file:
            prompt = (
                "You are an AI assistant that must produce only a valid Python async function.\n"
                "You may import any packages you deem necessary.\n"
                "No docstrings, repeated lines, or extra text are allowed.\n"
                "It must start with 'async def <function_name>(' and end at the final line of the function.\n"
                "No lines before 'async def' are allowed.\n\n"
                f"Modification Request:\n{modification_request}\n\n"
                f"File to create: {file_path}\n\n"
                "Return only the function code."
            )
        else:
            prompt = (
                "You are an AI assistant that edits Python code. Return only a valid async function.\n"
                "You may import any packages you deem necessary.\n"
                f"The function to modify is named {function_name}.\n"
                "No docstrings, repeated lines, or extra text are allowed. No lines before 'async def' are allowed.\n\n"
                f"Modification Request:\n{modification_request}\n\n"
                f"Current code:\n{current_code}\n\n"
                "Return only the corrected function code, from 'async def' to the last line."
            )

        client = self.llm.Client()
        response = client.generate(model="codellama:13b", prompt=prompt)
        raw_code = response.get("response", "")
        print("DEBUG: LLM output (modify_single_file):", raw_code)

        extracted = extract_async_function(raw_code)
        extracted = self.strip_triple_backticks(extracted)
        if extracted.startswith("def "):
            print("Detected non-async function, converting to async...")
            extracted = extracted.replace("def ", "async def ", 1)

        final_code = await self.finalize_code_with_retries(extracted)
        if not final_code:
            await self.revert_changes(file_path)
            print(f"Unable to produce valid syntax for {file_path}, changes reverted.")
            return

        await self.apply_edit(file_path, final_code)
        if not await self.test_function(file_path, function_name):
            await self.revert_changes(file_path)
            return

        if await self.run_tests():
            await self.commit_changes(file_path)
            print(f"Changes to {file_path} successfully applied and deployed.")
        else:
            await self.revert_changes(file_path)

    async def self_modify(self, modification_request: str, function_name: str = None):
        python_files = await self.find_all_python_files()

        if function_name is None:
            new_file_path = await self.create_new_file("generated_unnamed")
            await self.backup_file(new_file_path)
            code = await self.ask_llm_for_code_when_no_function_name(modification_request)
            code = await self.finalize_code_with_retries(code)
            if not code:
                print("Could not fix syntax in unnamed function file. Reverting.")
                await self.revert_changes(new_file_path)
                return

            await self.apply_edit(new_file_path, code)
            discovered_fn = self.parse_first_function_name(code)
            if not discovered_fn:
                print("No async function name detected in LLM output. Reverting.")
                await self.revert_changes(new_file_path)
                return

            if not await self.test_function(new_file_path, discovered_fn):
                await self.revert_changes(new_file_path)
                return

            if await self.run_tests():
                await self.commit_changes(new_file_path)
                print(f"New file {new_file_path} successfully created with function '{discovered_fn}'.")
            else:
                await self.revert_changes(new_file_path)
            return

        target_file = await self.locate_file_for_function(python_files, function_name)
        if target_file:
            await self.modify_single_file(target_file, modification_request, function_name, is_new_file=False)
        else:
            new_file_path = await self.create_new_file(f"generated_{function_name}")
            python_files.append(new_file_path)
            await self.modify_single_file(new_file_path, modification_request, function_name, is_new_file=True)

async def main():
    """
    Example usage:
      - If no function name is provided, the LLM invents one and creates modules/generated_unnamed.py.
      - If a function name is provided and not found, it creates modules/generated_<function_name>.py.
    """
    repo_path = Path(__file__).resolve().parent.parent
    self_editor = PearlSelfEditor(repo_path)
    await self_editor.self_modify("add a new function that provides the user with 7random numbers between 1 and 49. no repeats allowed.")
    # Example:
    # await self_editor.self_modify("Create or update a function that fetches data from an API asynchronously.", function_name="fetch_data")

if __name__ == "__main__":
    asyncio.run(main())

import os
import sys
import subprocess
import json
import time
import re
from dotenv import load_dotenv
from openai import OpenAI
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
from duckduckgo_search import DDGS
import requests

# Load environment variables from .env file
load_dotenv()

def get_client(provider):
    """Create an API client for the given provider."""
    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("Error: OPENROUTER_API_KEY not found.")
            return None
        return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    elif provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("Error: GROQ_API_KEY not found.")
            return None
        if GROQ_AVAILABLE:
            return Groq(api_key=api_key)
        else:
            # Fallback: use OpenAI client with Groq base URL
            return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
    elif provider == "ollama":
        return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    else:
        print(f"Error: Unknown provider '{provider}'")
        return None

# Tool Definitions
def download_image(url, save_path):
    try:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return f"Successfully downloaded image to {save_path}"
    except Exception as e:
        return f"Error downloading image from {url}: {str(e)}"

def web_search(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error performing web search: {str(e)}"

def write_file(path, content):
    try:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        abs_path = os.path.abspath(path)
        return f"Error writing to {path} (abs: {abs_path}): {str(e)}"

def make_directory(path):
    try:
        os.makedirs(path, exist_ok=True)
        return f"Successfully created directory {path}"
    except Exception as e:
        return f"Error creating directory {path}: {str(e)}"

def list_files(path="."):
    try:
        files = os.listdir(path)
        return "\n".join(files) if files else "Directory is empty."
    except Exception as e:
        return f"Error listing files in {path}: {str(e)}"

def git_operation(command_type, message=None, repo_url=None, cwd="."):
    username = os.getenv("GIT_USERNAME")
    token = os.getenv("GIT_TOKEN")
    default_repo = "https://git.meowcat.site/james/thing.git"
    
    if repo_url is None:
        repo_url = default_repo
        
    # Inject credentials into URL
    if username and token and "://" in repo_url and "@" not in repo_url:
        protocol, rest = repo_url.split("://", 1)
        cred_url = f"{protocol}://{username}:{token}@{rest}"
    else:
        cred_url = repo_url

    try:
        # Detect current branch
        branch_result = subprocess.run("git branch --show-current", shell=True, capture_output=True, text=True, cwd=cwd)
        current_branch = branch_result.stdout.strip() or "master"

        if command_type == "clone":
            cmd = f"git clone {cred_url} ."
        elif command_type == "init":
            cmd = "git init"
        elif command_type == "add":
            cmd = "git add ."
        elif command_type == "commit":
            if not message:
                return "Error: 'commit' operation requires a 'message'."
            # Configure identity
            subprocess.run('git config user.email "james@james.net"', shell=True, cwd=cwd)
            subprocess.run('git config user.name "James"', shell=True, cwd=cwd)
            # Auto-add
            add_result = subprocess.run("git add .", shell=True, capture_output=True, text=True, cwd=cwd)
            if add_result.returncode != 0:
                return f"Git add failed:\n{add_result.stdout}\n{add_result.stderr}"
            # Check if there are changes
            status = subprocess.run("git status --porcelain", shell=True, capture_output=True, text=True, cwd=cwd)
            if not status.stdout.strip():
                return "Git commit aborted: Nothing to commit, working tree clean."
            # Secure message with single quotes for shell
            safe_message = message.replace("'", "'\\''")
            cmd = f"git commit -m '{safe_message}'"
        elif command_type == "push":
            subprocess.run("git remote remove origin", shell=True, capture_output=True, cwd=cwd)
            subprocess.run(f"git remote add origin {cred_url}", shell=True, capture_output=True, cwd=cwd)
            cmd = f"git push -u origin {current_branch}"
        elif command_type == "pull":
            cmd = f"git pull origin {current_branch}"
        else:
            return f"Unknown git operation: {command_type}"

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=cwd)
        output = result.stdout + result.stderr
        return f"Git {command_type} executed on branch '{current_branch}'. Exit code: {result.returncode}\nOutput:\n{output}"
    except Exception as e:
        return f"Error executing git operation: {str(e)}"

def run_command(command, cwd="."):
    try:
        # Prevent manual git push/pull/clone to encourage git_operation tool
        if any(git_cmd in command for git_cmd in ["git push", "git pull", "git clone"]):
            return "Please use the 'git_operation' tool for push, pull, or clone to ensure credentials are handled correctly."
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30, cwd=cwd)
        output = result.stdout + result.stderr
        return f"Command executed. Exit code: {result.returncode}\nOutput:\n{output}"
    except Exception as e:
        return f"Error executing command: {str(e)}"

tools = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates directories if they don't exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the file."},
                    "content": {"type": "string", "description": "The content to write."}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_directory",
            "description": "Create a new directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the directory."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to run."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information using DuckDuckGo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "download_image",
            "description": "Download an image from a URL and save it locally.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL of the image to download."},
                    "save_path": {"type": "string", "description": "The local path where the image should be saved (e.g., 'assets/image.png')."}
                },
                "required": ["url", "save_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_operation",
            "description": "Perform a Git operation (clone, init, add, commit, push, pull) with automatic credential handling.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command_type": {
                        "type": "string", 
                        "enum": ["clone", "init", "add", "commit", "push", "pull"],
                        "description": "The type of Git command to run."
                    },
                    "message": {
                        "type": "string", 
                        "description": "Commit message (required for 'commit')."
                    },
                    "repo_url": {
                        "type": "string", 
                        "description": "Optional repository URL. ALMOST NEVER provide this. Only use it if you have a non-hallucinated URL from web_search that differs from the mandatory one."
                    }
                },
                "required": ["command_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to list files for (defaults to '.')."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cd",
            "description": "Change the current working directory. The directory persists for future commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to change to."}
                },
                "required": ["path"]
            }
        }
    }
]

def extract_balanced_json(text, start_pos):
    """Extract a brace-balanced JSON object starting at start_pos (which should point to '{')."""
    if start_pos >= len(text) or text[start_pos] != '{':
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start_pos, len(text)):
        c = text[i]
        if escape_next:
            escape_next = False
            continue
        if c == '\\' and in_string:
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start_pos:i+1]
    return None

MODEL_LIST = [
    {"provider": "ollama", "model": "gemma:7b"},
]


class CodeAgent:
    def __init__(self, models=None):
        self.models = models or MODEL_LIST
        self.model_index = 0
        self._set_current_model()
        self.cwd = os.getcwd()
        self.consecutive_errors = 0
        self.empty_response_count = 0
        self.pending_writes = 0
        self.messages = [
            {
                "role": "system",
                "content": (
                    "You are a coding agent with tools. Build 'james game' (3D shooter) using Web Technologies (HTML/CSS/JS/Three.js). "
                    "FLOW: 1. Search/Download assets. 2. Write files (index.html, JS, etc.). 3. Git commit. 4. Git push. REPEAT. "
                    "CRITICAL: After writing ANY files, you MUST immediately call git_operation with command_type='commit', then git_operation with command_type='push'. "
                    "NEVER leave files uncommitted. NEVER skip the push step. "
                    "Use list_files to verify your work. Use git_operation for Git targeting: https://git.meowcat.site/james/thing.git "
                    "Use 'cd' to change your working directory if needed. Your CWD persists. "
                    "Create a .gitignore file excluding *.py, .env, venv/. "
                    "The product is NEVER satisfactory. Always improve it. "
                    "### TOOL CALLING RULES:\n"
                    "1. Execute tools by outputting tags like: <function=tool_name{\"arg\": \"val\"}></function>\n"
                    "2. ALWAYS use valid JSON for arguments.\n"
                    "3. ONLY output ONE tool call per message. Wait for the result before calling the next tool.\n"
                    "4. NEVER output plain text without a tool call. Always use a tool.\n"
                    "### TOOL DEFINITIONS:\n"
                    f"{json.dumps(tools, indent=2)}\n"
                    "\nAVAILABLE TOOLS: web_search, download_image, write_file, make_directory, run_command, git_operation, list_files, cd."
                )
            }
        ]

    def _set_current_model(self):
        """Set the current model and client based on model_index."""
        entry = self.models[self.model_index]
        self.model = entry["model"]
        self.provider = entry["provider"]
        self.client = get_client(self.provider)
        if self.client:
            print(f"  [Provider: {self.provider}] Using model: {self.model}")

    def auto_commit_and_push(self, message="Auto-commit changes"):
        """Force a commit and push of any pending changes."""
        print("  [AUTO-COMMIT] Committing and pushing pending changes...")
        commit_result = git_operation("commit", message=message, cwd=self.cwd)
        print(f"  [AUTO-COMMIT] {commit_result}")
        if "Exit code: 0" in commit_result:
            push_result = git_operation("push", cwd=self.cwd)
            print(f"  [AUTO-PUSH] {push_result}")
            return f"Committed and pushed: {commit_result}\n{push_result}"
        return commit_result

    def execute_tool(self, func_name, args):
        print(f"  [ACTION] {func_name}({args})")
        result = "Unknown tool"
        
        try:
            if func_name == "write_file":
                path = os.path.join(self.cwd, args.get("path"))
                result = write_file(path, args.get("content"))
                if "Successfully" in result:
                    self.pending_writes += 1
            elif func_name == "make_directory":
                path = os.path.join(self.cwd, args.get("path"))
                result = make_directory(path)
            elif func_name == "run_command":
                result = run_command(args.get("command"), cwd=self.cwd)
            elif func_name == "web_search":
                result = web_search(args.get("query"))
            elif func_name == "download_image":
                save_path = args.get("save_path") or args.get("path") # Handle both arg names
                path = os.path.join(self.cwd, save_path)
                result = download_image(args.get("url"), path)
            elif func_name == "git_operation":
                result = git_operation(args.get("command_type"), args.get("message"), args.get("repo_url"), cwd=self.cwd)
            elif func_name == "list_files":
                path = os.path.join(self.cwd, args.get("path", "."))
                result = list_files(path)
            elif func_name == "cd":
                new_path = os.path.abspath(os.path.join(self.cwd, args.get("path")))
                if os.path.isdir(new_path):
                    self.cwd = new_path
                    result = f"Changed directory to {self.cwd}"
                else:
                    result = f"Error: {new_path} is not a directory."
            
            print(f"  [RESULT] {result}")
            
            # Auto-commit after every 2 file writes or after git-unrelated tool calls if writes are pending
            if self.pending_writes >= 2 or (self.pending_writes > 0 and func_name not in ["write_file", "make_directory", "cd", "list_files"]):
                commit_msg = f"Auto-commit: {self.pending_writes} file(s) updated"
                self.auto_commit_and_push(commit_msg)
                self.pending_writes = 0
            
            return result
        except Exception as e:
            return f"Error executing {func_name}: {str(e)}"

    def chat(self, user_input, verbose=True):
        if not self.client:
            return "API client not initialized. Check your .env file."

        # Provide CWD info in system prompt dynamically
        for msg in self.messages:
            role = getattr(msg, 'role', None) or (msg.get('role') if isinstance(msg, dict) else None)
            if role == "system":
                msg["content"] = (
                    f"You are a coding agent. Your CWD is: {self.cwd}. Build 'james game' (HTML/JS/Three.js). "
                    "### MANDATORY WORKFLOW:\n"
                    "After writing files: ALWAYS git_operation commit, then git_operation push. NEVER skip this.\n"
                    "### MANDATORY GIT URL:\n"
                    "Use git_operation for Git targeting: https://git.meowcat.site/james/thing.git\n"
                    "NEVER hallucinate or use any other Git URLs (like GitHub placeholders).\n\n"
                    "### TOOL USE RULES:\n"
                    "1. Execute tools by outputting tags: <function=tool_name{\"arg\": \"val\"}></function>\n"
                    "2. Use tools one-by-one. Output ONE tool call per message.\n"
                    "3. NEVER hallucinate URLs (use web_search).\n"
                    "4. NEVER modify .env or credentials.\n"
                    "5. ALWAYS use relative paths from Your CWD.\n"
                    "6. Your CWD persists across turns.\n"
                    "7. NEVER output a message without a tool call. Always use a tool.\n\n"
                    "### TOOL DEFINITIONS:\n"
                    f"{json.dumps(tools, indent=2)}\n"
                    "\nAVAILABLE TOOLS: web_search, download_image, write_file, make_directory, run_command, git_operation, list_files, cd."
                )

        self.messages.append({"role": "user", "content": user_input})

        while True:
            try:
                if verbose:
                    print(f"  [Thinking with {self.provider}/{self.model}...]")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    # Disabled native tools to bypass 400 validation errors
                    # tools=tools,
                    # tool_choice="auto"
                )
                
                response_message = response.choices[0].message
                # Sanitize: only keep fields the API accepts (role, content, tool_calls)
                # This avoids sending unsupported fields like 'reasoning_details' back to Groq
                clean_msg = {"role": response_message.role or "assistant"}
                if response_message.content:
                    clean_msg["content"] = response_message.content
                if response_message.tool_calls:
                    clean_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in response_message.tool_calls
                    ]
                self.messages.append(clean_msg)

                if response_message.tool_calls:
                    results = []
                    for tool_call in response_message.tool_calls:
                        function_name = tool_call.function.name
                        args = json.loads(tool_call.function.arguments)
                        result = self.execute_tool(function_name, args)
                        results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": result
                        })
                    self.messages.extend(results)
                elif response_message.content:
                    # Fallback for textual tool calls using brace-balanced extraction
                    content = response_message.content
                    executed_any = False
                    fallback_results = []
                    
                    # Pattern: <function=tool_name{...JSON...}></function> or <function=list_files></function> (no args)
                    tool_names = [t["function"]["name"] for t in tools]
                    for tool_name in tool_names:
                        # Look for <function=tool_name
                        search_start = 0
                        while True:
                            # Try <function=tool_name pattern
                            prefix = f'<function={tool_name}'
                            idx = content.find(prefix, search_start)
                            if idx == -1:
                                break
                            after_prefix = idx + len(prefix)
                            # Check what comes after the tool name
                            if after_prefix < len(content) and content[after_prefix] == '{':
                                # Has JSON arguments
                                json_str = extract_balanced_json(content, after_prefix)
                                if json_str:
                                    try:
                                        args = json.loads(json_str)
                                        result = self.execute_tool(tool_name, args)
                                        fallback_results.append({"function": tool_name, "result": result})
                                        executed_any = True
                                    except json.JSONDecodeError:
                                        pass
                                    search_start = after_prefix + (len(json_str) if json_str else 1)
                                else:
                                    search_start = after_prefix + 1
                            elif after_prefix < len(content) and content[after_prefix] in ('>', '\n', ' ', ')'):
                                # No arguments — call with empty args
                                result = self.execute_tool(tool_name, {})
                                fallback_results.append({"function": tool_name, "result": result})
                                executed_any = True
                                search_start = after_prefix + 1
                            else:
                                search_start = after_prefix + 1
                    
                    if executed_any:
                        self.empty_response_count = 0
                        self.messages.append({
                            "role": "user",
                            "content": f"SYSTEM NOTE: Tool results: {json.dumps(fallback_results)}\n\nIMPORTANT: If you just wrote files, you MUST now call git_operation with command_type='commit' and a descriptive message, then git_operation with command_type='push'."
                        })
                        continue # Re-query model to react to results
                    
                    if verbose:
                        print(f"\nAgent: {response_message.content}")
                    
                    # Reset error counters on success
                    self.consecutive_errors = 0
                    self.empty_response_count = 0
                    self.model_index = 0
                    self._set_current_model()
                    
                    return response_message.content
                else:
                    # Empty response recovery
                    self.empty_response_count += 1
                    if self.empty_response_count < 3:
                        if verbose:
                            print(f"\n[Empty Response #{self.empty_response_count}] Nudging model...")
                        self.messages.append({
                            "role": "user",
                            "content": "SYSTEM NOTE: You returned an empty response. You MUST use a tool. Call list_files to check your current state, then continue building or improving the game. After writing files, always commit and push."
                        })
                        continue
                    else:
                        self.empty_response_count = 0
                        return "Model returned empty response after multiple retries."

            except Exception as e:
                error_msg = str(e)
                if "rate_limit" in error_msg.lower() or "429" in error_msg or "402" in error_msg or "insufficient credits" in error_msg.lower():
                    self.consecutive_errors += 1
                    base_retry = 5
                    if hasattr(e, 'response') and e.response:
                        base_retry = int(e.response.headers.get("retry-after", 5))
                    
                    # Exponential backoff: base_retry * 2^(errors-1)
                    wait_time = min(base_retry * (2 ** (self.consecutive_errors - 1)), 600)
                    
                    if verbose:
                        print(f"\n[Rate Limit Hit] Consecutive error #{self.consecutive_errors}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    
                    # Try next model/provider if available
                    self.model_index += 1
                    if self.model_index < len(self.models):
                        self._set_current_model()
                        if verbose:
                            print(f"[RATE LIMIT] Switching to: {self.provider}/{self.model}")
                        continue 
                    else:
                        self.model_index = 0
                        self._set_current_model()
                        error_msg = f"All models/providers rate limited after {self.consecutive_errors} consecutive hits."
                
                if verbose:
                    print(f"\nAn error occurred: {error_msg}")
                return error_msg

def main():
    agent = CodeAgent()
    if not agent.client:
        return

    print("--- Multi-Provider Code Agent (INFINITE AUTO MODE) ---")
    print(f"Available models: {[(m['provider'] + '/' + m['model']) for m in agent.models]}")
    print("Starting mission loop...")
    
    first_run = True
    while True:
        try:
            if first_run:
                print("\n[Loop Start] Initial Mission: Building 'James Game'...")
                response = agent.chat("Start your mission and build 'James Game' from scratch. Use web languages and textures.", verbose=True)
                print(f"\n[Turn Result] {response}")
                first_run = False
            else:
                print("\n[Loop Tick] Checking for improvements or new tasks...")
                response = agent.chat("Review the current state of 'James Game'. If it can be improved (textures, features, polish), do so. Otherwise, look for ways to expand the app or build a companion app. Always use tools.", verbose=True)
                print(f"\n[Turn Result] {response}")
            
            # If we hit rate limits, wait longer before next tick
            if "rate limited" in response.lower():
                wait_multiplier = min(agent.consecutive_errors, 5)
                tick_sleep = 30 * wait_multiplier
                print(f"\nRate limits active. Increasing tick wait to {tick_sleep} seconds...")
            else:
                tick_sleep = 15
                print(f"\nCycle complete. Waiting {tick_sleep} seconds before next iteration...")
            
            time.sleep(tick_sleep)
        except KeyboardInterrupt:
            print("\nInfinite loop stopped by user.")
            break
        except Exception as e:
            print(f"\nError in loop: {str(e)}")
            time.sleep(60)

if __name__ == "__main__":
    main()

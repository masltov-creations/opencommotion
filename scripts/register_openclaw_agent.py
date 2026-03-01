import os
import json
import subprocess
from pathlib import Path
import sys

# Add root for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.agents.visual.worker import _visual_dsl_system_prompt

def get_wsl_home() -> str:
    try:
        home_path = subprocess.check_output(["wsl", "--", "bash", "-lc", "echo -n $HOME"], text=True).strip()
        return home_path
    except Exception as e:
        print(f"Failed to find WSL home: {e}")
        return "/home/user"


def add_opencommotion_agent(model_id: str) -> None:
    home = get_wsl_home()
    
    # 1. Update openclaw.json
    try:
        # Fetch json using WSL
        oc_json_str = subprocess.check_output(["wsl", "--", "cat", f"{home}/.openclaw/openclaw.json"], text=True)
        conf = json.loads(oc_json_str)
        agents = conf.get("agents", {}).get("list", [])
        
        # Check if exists
        exists = any(a.get("id") == "opencommotion-visual" for a in agents)
        if not exists:
            agents.append({
                "id": "opencommotion-visual",
                "name": "OpenCommotion Visual",
                "model": {
                    "primary": model_id,
                    "fallbacks": []
                }
            })
            if "agents" not in conf:
                conf["agents"] = {}
            conf["agents"]["list"] = agents
            
            # Write back
            temp_path = "temp_oc.json"
            Path(temp_path).write_text(json.dumps(conf, indent=2))
            # Convert Windows to WSL path
            win_abs = Path(temp_path).resolve()
            wsl_path = subprocess.check_output(["wsl", "wslpath", "-a", "-u", str(win_abs)], text=True).strip()
            
            subprocess.check_call(["wsl", "--", "cp", wsl_path, f"{home}/.openclaw/openclaw.json"])
            os.remove(temp_path)
            print(f"Added 'opencommotion-visual' using model '{model_id}' to openclaw.json")
        else:
            print(f"Agent 'opencommotion-visual' already exists in openclaw.json.")
            
    except Exception as e:
        print(f"Warning: Could not auto-register agent in openclaw.json: {e}")
        
    # 2. Replicate standard agent files using built-in command to avoid manually building auth schema
    try:
        # 3. Create instruction workspace
        workspace = f"{home}/.openclaw/workspace-opencommotion-visual"
        subprocess.check_call(["wsl", "--", "mkdir", "-p", workspace])
        
        # Remove anything there to be safe
        subprocess.check_call(["wsl", "--", "bash", "-c", f"rm -f {workspace}/AGENTS.md {workspace}/BOOTSTRAP.md {workspace}/IDENTITY.md {workspace}/TOOLS.md {workspace}/USER.md {workspace}/HEARTBEAT.md"])
        
        prompt = _visual_dsl_system_prompt()
        strict_header = (
            "# STRICT BEHAVIOR OVERRIDE\n\n"
            "You are NOT a conversational assistant. You do NOT have opinions.\n"
            "You ONLY output JSON strings conforming to the OpenCommotion visual DSL.\n"
            "Never wrap your response in markdown fences or explanations.\n\n"
        )
        payload = strict_header + prompt
        
        temp_soul = "temp_soul.md"
        Path(temp_soul).write_text(payload, encoding="utf-8")
        win_abs = Path(temp_soul).resolve().as_posix()
        wsl_path = subprocess.check_output(["wsl", "wslpath", "-a", "-u", win_abs], text=True).strip()
        subprocess.check_call(["wsl", "--", "cp", wsl_path, f"{workspace}/SOUL.md"])
        os.remove(temp_soul)
        
        print("Successfully synchronized visual DSL rules to OpenClaw workspace.")
    except Exception as e:
        print(f"Warning: Failed to synchronize workspace files: {e}")

if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "github-copilot/gpt-4o"
    add_opencommotion_agent(model)

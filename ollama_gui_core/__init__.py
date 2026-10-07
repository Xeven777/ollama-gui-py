import json
import urllib.parse
import urllib.request
from typing import Generator, List, Dict, Any, Optional

class OllamaAPI:
    def __init__(self, host: str = "http://127.0.0.1:11434"):
        self.host = host.rstrip("/")

    def set_host(self, host: str):
        self.host = host.rstrip("/")

    def fetch_models(self) -> List[str]:
        url = urllib.parse.urljoin(self.host + "/", "api/tags")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.load(response)
            return [model["name"] for model in data.get("models", [])]

    def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        stop_flag_callback: Optional[callable] = None,
    ) -> Generator[str, None, None]:
        url = urllib.parse.urljoin(self.host + "/", "api/chat")

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        options: Dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature

        if options:
            payload["options"] = options

        # If system prompt is provided and not empty, inject or update system message
        if system_prompt and system_prompt.strip():
            # Check if messages already start with a system message
            if messages and messages[0].get("role") == "system":
                payload["messages"] = [{"role": "system", "content": system_prompt}] + messages[1:]
            else:
                payload["messages"] = [{"role": "system", "content": system_prompt}] + messages

        request_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=request_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            for line in resp:
                if stop_flag_callback and stop_flag_callback():
                    break
                if line:
                    data = json.loads(line.decode("utf-8"))
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]

    def delete_model(self, model_name: str) -> bool:
        url = urllib.parse.urljoin(self.host + "/", "api/delete")
        req = urllib.request.Request(
            url,
            data=json.dumps({"name": model_name}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="DELETE",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status in (200, 204)

    def pull_model_stream(self, model_name: str, insecure: bool = False) -> Generator[Dict[str, Any], None, None]:
        url = urllib.parse.urljoin(self.host + "/", "api/pull")
        req = urllib.request.Request(
            url,
            data=json.dumps({"name": model_name, "insecure": insecure, "stream": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as response:
            for line in response:
                if line:
                    yield json.loads(line.decode("utf-8"))

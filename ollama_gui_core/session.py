import uuid
from typing import List, Dict, Optional, Any

class ChatSession:
    def __init__(self, session_id: Optional[str] = None, title: str = "New Chat"):
        self.id = session_id or str(uuid.uuid4())
        self.title = title
        self.messages: List[Dict[str, str]] = []
        self.system_prompt: str = ""
        self.temperature: float = 0.7

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if self.title == "New Chat" and role == "user" and content:
            # Auto generate title based on first query
            self.title = content[:28].replace("\n", " ").strip() + ("..." if len(content) > 28 else "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "messages": self.messages,
            "system_prompt": self.system_prompt,
            "temperature": self.temperature,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSession":
        session = cls(session_id=data.get("id"), title=data.get("title", "New Chat"))
        session.messages = data.get("messages", [])
        session.system_prompt = data.get("system_prompt", "")
        session.temperature = data.get("temperature", 0.7)
        return session


class ChatManager:
    def __init__(self):
        self.sessions: List[ChatSession] = []
        self.active_session_id: Optional[str] = None
        self.create_new_session()

    def create_new_session(self, title: str = "New Chat") -> ChatSession:
        session = ChatSession(title=title)
        self.sessions.insert(0, session)
        self.active_session_id = session.id
        return session

    def get_active_session(self) -> ChatSession:
        for s in self.sessions:
            if s.id == self.active_session_id:
                return s
        if not self.sessions:
            return self.create_new_session()
        self.active_session_id = self.sessions[0].id
        return self.sessions[0]

    def set_active_session(self, session_id: str) -> Optional[ChatSession]:
        for s in self.sessions:
            if s.id == session_id:
                self.active_session_id = session_id
                return s
        return None

    def delete_session(self, session_id: str):
        self.sessions = [s for s in self.sessions if s.id != session_id]
        if self.active_session_id == session_id:
            if self.sessions:
                self.active_session_id = self.sessions[0].id
            else:
                self.create_new_session()

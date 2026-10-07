import sys
import json
import time
import threading
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from tkinter import messagebox, filedialog
from typing import Optional, List, Dict, Any

import customtkinter as ctk

try:
    import mistune as _mistune_mod

    _MD_PARSER = _mistune_mod.create_markdown(
        renderer="ast", plugins=["table", "strikethrough", "task_lists"]
    )
except Exception:  # markdown unavailable -> plain-text fallback
    _mistune_mod = None
    _MD_PARSER = None

from ollama_gui_core import OllamaAPI
from ollama_gui_core.session import ChatManager, ChatSession

__version__ = "2.0.0"

# Configure CustomTkinter defaults
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ModelManagementDialog(ctk.CTkToplevel):
    def __init__(self, parent, api: OllamaAPI, on_models_updated=None):
        super().__init__(parent)
        self.api = api
        self.on_models_updated = on_models_updated

        self.title("Model Management")
        self.geometry("520x580")
        self.resizable(False, False)

        # Center dialog on parent window
        self.transient(parent)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Download frame
        download_frame = ctk.CTkFrame(self, fg_color="transparent")
        download_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        download_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            download_frame, text="Download New Model", font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        self.model_entry = ctk.CTkEntry(
            download_frame, placeholder_text="e.g., llama3, mistral, gemma:2b"
        )
        self.model_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        self.download_btn = ctk.CTkButton(
            download_frame, text="Pull Model", width=100, command=self.on_download
        )
        self.download_btn.grid(row=1, column=1)

        # Installed models frame
        list_frame = ctk.CTkFrame(self, fg_color="transparent")
        list_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        list_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            list_frame, text="Installed Models", font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.models_textbox = ctk.CTkTextbox(list_frame, height=100)
        self.models_textbox.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        btn_box = ctk.CTkFrame(list_frame, fg_color="transparent")
        btn_box.grid(row=1, column=1, sticky="n")

        self.delete_btn = ctk.CTkButton(
            btn_box, text="Delete", fg_color="#E53935", hover_color="#C62828", width=100, command=self.on_delete
        )
        self.delete_btn.pack(pady=2)

        self.refresh_btn = ctk.CTkButton(
            btn_box, text="Refresh", fg_color="#333333", hover_color="#555555", width=100, command=self.refresh_models
        )
        self.refresh_btn.pack(pady=5)

        # Log frame
        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            log_frame, text="Operation Log", font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        self.log_box = ctk.CTkTextbox(log_frame, state="disabled")
        self.log_box.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self.refresh_models()

    def log(self, text: str, clear: bool = False):
        # Tkinter isn't thread-safe — marshal background-thread calls to the UI thread.
        if threading.current_thread() is not threading.main_thread():
            self.after(0, lambda: self.log(text, clear))
            return
        self.log_box.configure(state="normal")
        if clear:
            self.log_box.delete("1.0", tk.END)
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def refresh_models(self):
        def _fetch():
            try:
                models = self.api.fetch_models()
                self.after(0, lambda: self._show_models(models))
            except Exception as e:
                self.after(0, lambda: self.log(f"Error fetching models: {e}"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _show_models(self, models):
        self.models_textbox.configure(state="normal")
        self.models_textbox.delete("1.0", tk.END)
        if models:
            self.models_textbox.insert(tk.END, "\n".join(models))
        else:
            self.models_textbox.insert(tk.END, "No models found.")
        self.models_textbox.configure(state="disabled")
        if self.on_models_updated:
            self.on_models_updated(models)

    def on_download(self):
        model = self.model_entry.get().strip()
        if not model:
            return

        if model.startswith("ollama run "):
            model = model[11:]
        elif model.startswith("ollama pull "):
            model = model[12:]

        self.download_btn.configure(state="disabled")
        self.log(f"Starting pull for '{model}'...", clear=True)

        def _pull():
            try:
                for chunk in self.api.pull_model_stream(model):
                    status = chunk.get("status", "")
                    completed = chunk.get("completed", 0)
                    total = chunk.get("total", 0)
                    if total > 0:
                        pct = int((completed / total) * 100)
                        self.log(f"{status} ({pct}%)")
                    elif status:
                        self.log(status)
                self.log(f"Successfully downloaded {model}!")
                self.after(0, self.refresh_models)
            except Exception as e:
                self.log(f"Download error: {e}")
            finally:
                self.after(0, lambda: self.download_btn.configure(state="normal"))

        threading.Thread(target=_pull, daemon=True).start()

    def on_delete(self):
        # Delete selected text in textbox or prompt entry
        selected = self.models_textbox.get("sel.first", "sel.last").strip() if self.models_textbox.tag_ranges("sel") else ""
        if not selected:
            selected = self.model_entry.get().strip()

        if not selected:
            messagebox.showwarning("Select Model", "Please highlight or enter a model name to delete.", parent=self)
            return

        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete model '{selected}'?", parent=self):
            return

        self.log(f"Deleting model '{selected}'...", clear=True)

        def _delete():
            try:
                if self.api.delete_model(selected):
                    self.log(f"Model '{selected}' deleted successfully.")
                    self.refresh_models()
                else:
                    self.log(f"Failed to delete model '{selected}'.")
            except Exception as e:
                self.log(f"Delete error: {e}")

        threading.Thread(target=_delete, daemon=True).start()


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, session: ChatSession, on_save_callback):
        super().__init__(parent)
        self.session = session
        self.on_save_callback = on_save_callback

        self.title("Chat & Model Parameters")
        self.geometry("480x420")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)

        # System Prompt
        ctk.CTkLabel(self, text="System Prompt", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=20, pady=(20, 5))
        self.system_prompt_box = ctk.CTkTextbox(self, height=140)
        self.system_prompt_box.pack(fill="x", padx=20, pady=(0, 15))
        self.system_prompt_box.insert("1.0", session.system_prompt)

        # Temperature
        temp_frame = ctk.CTkFrame(self, fg_color="transparent")
        temp_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(temp_frame, text="Temperature:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.temp_label = ctk.CTkLabel(temp_frame, text=f"{session.temperature:.2f}", font=ctk.CTkFont(size=13))
        self.temp_label.pack(side="right")

        self.temp_slider = ctk.CTkSlider(self, from_=0.0, to=2.0, number_of_steps=40, command=self._on_slider_change)
        self.temp_slider.set(session.temperature)
        self.temp_slider.pack(fill="x", padx=20, pady=(0, 20))

        # Save Button
        save_btn = ctk.CTkButton(self, text="Apply & Save", command=self._on_save, fg_color="#1F6AA5", hover_color="#144870")
        save_btn.pack(pady=10)

    def _on_slider_change(self, value):
        self.temp_label.configure(text=f"{value:.2f}")

    def _on_save(self):
        self.session.system_prompt = self.system_prompt_box.get("1.0", tk.END).strip()
        self.session.temperature = round(float(self.temp_slider.get()), 2)
        if self.on_save_callback:
            self.on_save_callback()
        self.destroy()


def _inline_plain(children) -> str:
    """Extract plain text from mistune inline tokens (for tables/measuring)."""
    parts: List[str] = []
    for ch in children or []:
        t = ch.get("type", "")
        if t == "text":
            parts.append(ch.get("raw", ""))
        elif t == "softbreak":
            parts.append(" ")
        elif t == "linebreak":
            parts.append("\n")
        elif t == "codespan":
            parts.append(ch.get("raw", ""))
        elif "children" in ch:
            parts.append(_inline_plain(ch.get("children")))
        elif "raw" in ch:
            parts.append(ch.get("raw", ""))
    return "".join(parts)


class ChatBubble(ctk.CTkFrame):
    """Single chat message bubble.

    Body is a plain ``tk.Text`` with NO scrollbar widget attached, so an
    inner scrollbar is impossible — long messages simply grow taller and the
    outer chat list scrolls. Assistant messages are rendered as markdown
    (mistune AST -> text tags); user messages are plain text.
    """

    _FONTS: Optional[Dict[str, Any]] = None

    def __init__(self, parent, role: str, content: str, on_copy=None, markdown: bool = True):
        is_user = role == "user"
        self.role = role
        self.content = content
        self._on_copy = on_copy
        # Only assistant messages get markdown; user input stays literal.
        self._use_markdown = markdown and not is_user
        self._links: List[tuple] = []
        self._fit_pending = False
        self._cap_px = 560

        pal = self._palette(is_user)
        super().__init__(
            parent,
            fg_color=pal["bubble"],
            border_width=1,
            border_color=pal["border"],
            corner_radius=12,
        )
        self._pal = pal

        # Role Header & Copy action (kept slim so short messages stay small)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(6, 0))

        avatar = "🧑" if is_user else "🤖"
        role_name = f"{avatar}  You" if is_user else f"{avatar}  Assistant"

        ctk.CTkLabel(
            header,
            text=role_name,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=pal["role"],
        ).pack(side="left")

        copy_btn = ctk.CTkButton(
            header,
            text="Copy",
            width=32,
            height=18,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=pal["copy_hover"],
            text_color=pal["dim"],
            command=self._do_copy,
        )
        copy_btn.pack(side="right")

        # Non-scrollable text body (selectable, read-only).
        self._text = tk.Text(
            self,
            wrap="word",
            relief="flat",
            bd=0,
            highlightthickness=0,
            takefocus=0,
            cursor="arrow",
            exportselection=True,
            padx=2,
            pady=2,
            background=pal["bubble"],
            foreground=pal["fg"],
            selectbackground=pal["select_bg"],
            selectforeground=pal["select_fg"],
            insertbackground=pal["fg"],
            spacing1=0,
            spacing2=0,
            spacing3=0,
            width=40,
            height=1,
        )
        self._text.pack(fill="x", expand=True, padx=10, pady=(0, 8))
        self._setup_tags()
        self._text.tag_bind("link", "<Button-1>", self._on_link_click)
        self._text.tag_bind("link", "<Enter>", lambda e: self._text.configure(cursor="hand2"))
        self._text.tag_bind("link", "<Leave>", lambda e: self._text.configure(cursor="arrow"))

        self._render_body(content)
        self._schedule_fit()

    # ---------- styling ----------

    @classmethod
    def _fonts(cls) -> Dict[str, Any]:
        if cls._FONTS is None:
            try:
                base = tkfont.Font(font="TkDefaultFont")
            except Exception:
                base = tkfont.Font()
            base.configure(size=13)
            try:
                bold = tkfont.Font(font="TkDefaultFont")
            except Exception:
                bold = tkfont.Font()
            bold.configure(size=13, weight="bold")
            try:
                italic = tkfont.Font(font="TkDefaultFont")
            except Exception:
                italic = tkfont.Font()
            italic.configure(size=13, slant="italic")
            try:
                code = tkfont.Font(font="TkFixedFont")
            except Exception:
                code = tkfont.Font(family="Courier")
            code.configure(size=12)
            fam = base.cget("family")
            h1 = tkfont.Font(family=fam, size=17, weight="bold")
            h2 = tkfont.Font(family=fam, size=15, weight="bold")
            h3 = tkfont.Font(family=fam, size=13, weight="bold")
            small = tkfont.Font(family=fam, size=11)
            cls._FONTS = {
                "base": base, "bold": bold, "italic": italic, "code": code,
                "h1": h1, "h2": h2, "h3": h3, "small": small,
            }
        return cls._FONTS

    @staticmethod
    def _palette(is_user: bool) -> Dict[str, str]:
        light = ctk.get_appearance_mode() == "Light"
        if light:
            if is_user:
                return {
                    "bubble": "#1F6AA5", "border": "#1F6AA5", "fg": "#FFFFFF",
                    "role": "#D6E9FF", "dim": "#BFD6EA", "copy_hover": "#18547F",
                    "code_bg": "#174E77", "code_fg": "#FFE1A8", "codelang": "#BFD6EA",
                    "quote": "#D6E9FF", "link": "#FFD98A", "hr": "#BFD6EA",
                    "select_bg": "#0F3D5C", "select_fg": "#FFFFFF",
                }
            return {
                "bubble": "#EDEFF3", "border": "#D3D9E1", "fg": "#16191D",
                "role": "#1E7E34", "dim": "#6B7280", "copy_hover": "#DDE2E9",
                "code_bg": "#DDE2E9", "code_fg": "#7C3A00", "codelang": "#6B7280",
                "quote": "#5B6470", "link": "#0B5CAD", "hr": "#9AA3AF",
                "select_bg": "#B9D4F0", "select_fg": "#101418",
            }
        if is_user:
            return {
                "bubble": "#1E4E79", "border": "#3A7AB5", "fg": "#FFFFFF",
                "role": "#9CC4FF", "dim": "#8FA8C4", "copy_hover": "#2A5A86",
                "code_bg": "#14334E", "code_fg": "#FFD98A", "codelang": "#8FA8C4",
                "quote": "#B9D2EC", "link": "#FFD98A", "hr": "#3A5A7A",
                "select_bg": "#0F3D5C", "select_fg": "#FFFFFF",
            }
        return {
            "bubble": "#22262E", "border": "#353C46", "fg": "#E4E7EB",
            "role": "#9EE6A8", "dim": "#7D8590", "copy_hover": "#31363F",
            "code_bg": "#14161B", "code_fg": "#E8C47A", "codelang": "#7D8590",
            "quote": "#9AA4B2", "link": "#6CB2FF", "hr": "#4A525E",
            "select_bg": "#264F78", "select_fg": "#FFFFFF",
        }

    def _setup_tags(self):
        f = self._fonts()
        p = self._pal
        t = self._text
        t.configure(font=f["base"])
        t.tag_configure("bold", font=f["bold"])
        t.tag_configure("italic", font=f["italic"])
        t.tag_configure("strike", overstrike=True)
        t.tag_configure("code_inline", font=f["code"], background=p["code_bg"], foreground=p["code_fg"])
        t.tag_configure("codeblock", font=f["code"], background=p["code_bg"],
                        foreground=p["code_fg"], lmargin1=10, lmargin2=10,
                        rmargin=10, spacing1=4, spacing3=4)
        t.tag_configure("codelang", font=f["small"], foreground=p["codelang"])
        t.tag_configure("h1", font=f["h1"], spacing1=8, spacing3=6)
        t.tag_configure("h2", font=f["h2"], spacing1=6, spacing3=4)
        t.tag_configure("h3", font=f["h3"], spacing1=4, spacing3=2)
        t.tag_configure("bullet", lmargin1=20, lmargin2=30, spacing1=1, spacing3=1)
        t.tag_configure("quote", foreground=p["quote"], lmargin1=16, lmargin2=16,
                        spacing1=4, spacing3=4)
        t.tag_configure("link", foreground=p["link"], underline=True)
        t.tag_configure("hr", foreground=p["hr"], spacing1=6, spacing3=6)
        # Priority: block/code styles win over inline emphasis so nested
        # styles (e.g. bold inside a heading) degrade gracefully.
        for tag in ("bullet", "quote", "hr", "bold", "italic", "strike",
                    "link", "code_inline", "codelang", "codeblock",
                    "h3", "h2", "h1"):
            try:
                t.tag_raise(tag)
            except Exception:
                pass

    # ---------- markdown rendering ----------

    def _insert(self, s: str, tags=()):
        if s:
            self._text.insert("end", s, tags)

    def _render_inline(self, children, tags=()):
        for ch in children or []:
            t = ch.get("type", "")
            if t == "text":
                self._insert(ch.get("raw", ""), tags)
            elif t == "softbreak":
                self._insert(" ", tags)
            elif t == "linebreak":
                self._insert("\n", tags)
            elif t == "codespan":
                self._insert(ch.get("raw", ""), tags + ("code_inline",))
            elif t == "strong":
                self._render_inline(ch.get("children"), tags + ("bold",))
            elif t == "emphasis":
                self._render_inline(ch.get("children"), tags + ("italic",))
            elif t == "strikethrough":
                self._render_inline(ch.get("children"), tags + ("strike",))
            elif t == "link":
                url = (ch.get("attrs") or {}).get("url", "")
                start = self._text.index("end-1c")
                self._render_inline(ch.get("children"), tags + ("link",))
                end = self._text.index("end-1c")
                if url:
                    self._links.append((start, end, url))
            elif t == "image":
                url = (ch.get("attrs") or {}).get("url", "")
                alt = _inline_plain(ch.get("children")) or "image"
                start = self._text.index("end-1c")
                self._insert(f"🖼 {alt}", tags + ("link",))
                end = self._text.index("end-1c")
                if url:
                    self._links.append((start, end, url))
            elif "children" in ch:
                self._render_inline(ch.get("children"), tags)
            elif "raw" in ch:
                self._insert(ch.get("raw", ""), tags)

    def _render_blocks(self, tokens, depth: int = 0):
        for tok in tokens or []:
            t = tok.get("type", "")
            attrs = tok.get("attrs") or {}
            if t == "heading":
                level = min(max(int(attrs.get("level", 2)), 1), 3)
                self._render_inline(tok.get("children"), (f"h{level}",))
                self._insert("\n")
            elif t == "paragraph":
                self._render_inline(tok.get("children"))
                self._insert("\n\n")
            elif t == "blank_line":
                pass
            elif t == "block_text":
                self._render_inline(tok.get("children"))
            elif t == "list":
                ordered = bool(attrs.get("ordered", False))
                depth = int(attrs.get("depth", depth))
                idx = 0
                for item in tok.get("children", []):
                    it = item.get("type", "")
                    if it == "task_list_item":
                        prefix = "☑ " if (item.get("attrs") or {}).get("checked") else "☐ "
                    elif ordered:
                        idx += 1
                        prefix = f"{idx}. "
                    else:
                        prefix = "• "
                    self._insert("  " * min(depth, 4) + prefix, ("bullet",))
                    kids = item.get("children", [])
                    first = True
                    for k in kids:
                        kt = k.get("type", "")
                        if kt == "block_text":
                            if not first:
                                self._insert("\n" + "  " * min(depth, 4) + "   ", ("bullet",))
                            self._render_inline(k.get("children"), ("bullet",))
                            first = False
                        elif kt == "list":
                            self._insert("\n")
                            self._render_blocks([k], depth + 1)
                        else:
                            self._insert("\n")
                            self._render_blocks([k], depth + 1)
                    if self._text.get("end-2c", "end-1c") != "\n":
                        self._insert("\n")
                self._insert("\n")
            elif t == "block_code":
                if self._text.get("end-2c", "end-1c") not in ("", "\n"):
                    self._insert("\n")
                info = str(attrs.get("info", "") or "").strip()
                if info:
                    self._insert(f"{info}\n", ("codeblock", "codelang"))
                code = tok.get("raw", "").strip("\n")
                self._insert(code if code else " ", ("codeblock",))
                self._insert("\n\n")
            elif t == "block_quote":
                start = self._text.index("end-1c")
                self._render_blocks(tok.get("children"), depth)
                if self._text.get("end-2c", "end-1c") != "\n":
                    self._insert("\n")
                try:
                    self._text.tag_add("quote", start, "end-1c")
                except Exception:
                    pass
                self._insert("\n")
            elif t == "thematic_break":
                self._insert("─" * 28 + "\n\n", ("hr",))
            elif t == "table":
                self._render_table(tok)
            elif t == "block_html":
                self._insert(tok.get("raw", ""), ("codeblock",))
                self._insert("\n\n")
            elif "children" in tok:
                self._render_blocks(tok.get("children"), depth)
            elif "raw" in tok:
                self._insert(tok.get("raw", ""))

    def _render_table(self, tok):
        rows: List[List[str]] = []
        is_header_row = True
        for section in tok.get("children", []):
            st = section.get("type", "")
            if st == "table_head":
                for row in section.get("children", []):
                    if row.get("type") == "table_row":
                        rows.append([_inline_plain(c.get("children")) for c in row.get("children", [])])
                        is_header_row = False
                # mistune table_head contains cells directly (no table_row wrapper)
                if is_header_row:
                    cells = [c for c in section.get("children", []) if c.get("type") == "table_cell"]
                    if cells:
                        rows.append([_inline_plain(c.get("children")) for c in cells])
                        is_header_row = False
            elif st in ("table_body", "table_row"):
                targets = section.get("children", []) if st == "table_body" else [section]
                for row in targets:
                    if row.get("type") == "table_row":
                        rows.append([_inline_plain(c.get("children")) for c in row.get("children", [])])
        if not rows:
            return
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        col_w = [max(len(r[i]) for r in rows) for i in range(width)]
        lines = []
        for i, r in enumerate(rows):
            lines.append(" | ".join(cell.ljust(col_w[j]) for j, cell in enumerate(r)))
            if i == 0:
                lines.append("-+-".join("-" * w for w in col_w))
        if self._text.get("end-2c", "end-1c") not in ("", "\n"):
            self._insert("\n")
        self._insert("\n".join(lines) + "\n\n", ("codeblock",))

    def _render_body(self, content: str):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._links = []
        if self._use_markdown and _MD_PARSER is not None:
            try:
                self._render_blocks(_MD_PARSER(content or ""))
            except Exception:
                self._text.delete("1.0", "end")
                self._text.insert("1.0", content)
        else:
            self._text.insert("1.0", content)
        # Strip trailing blank lines so the bubble hugs its content.
        try:
            while self._text.get("end-2c", "end-1c") == "\n":
                self._text.delete("end-2c", "end-1c")
        except Exception:
            pass
        self._text.configure(state="disabled")

    # ---------- interaction ----------

    def _do_copy(self):
        if self._on_copy:
            self._on_copy(self.content)

    def _on_link_click(self, event):
        try:
            idx = self._text.index(f"@{event.x},{event.y}")
            for start, end, url in self._links:
                if (self._text.compare(idx, ">=", start)
                        and self._text.compare(idx, "<", end)):
                    webbrowser.open(url)
                    break
        except Exception:
            pass
        return "break"

    # ---------- sizing (no inner scrollbar; grow to fit) ----------

    def adapt_width(self, row_width: int):
        """Cap bubble width to a fraction of the chat row width."""
        try:
            self._cap_px = max(220, int(row_width * 0.78) - 24)
        except Exception:
            self._cap_px = 560
        self._schedule_fit()

    def _schedule_fit(self):
        if self._fit_pending:
            return
        self._fit_pending = True
        try:
            self.after_idle(self._do_fit)
        except Exception:
            self._fit_pending = False

    def _do_fit(self):
        self._fit_pending = False
        try:
            if not self.winfo_exists():
                return
            fonts = self._fonts()
            cw = max(5, fonts["base"].measure("n"))
            cap_chars = max(24, self._cap_px // cw)
            content = self._text.get("1.0", "end-1c")
            longest = 0
            for line in content.split("\n"):
                w = fonts["base"].measure(line if line else " ")
                if w > longest:
                    longest = w
            longest = int(longest * 1.1)  # margin for larger heading/mono fonts
            need_chars = longest // cw + 3
            width_chars = min(cap_chars, max(need_chars, 12))
            if int(self._text.cget("width")) != width_chars:
                self._text.configure(width=width_chars)
            self._text.update_idletasks()
            # Safety net: measure the real requested pixels and shrink until
            # the bubble fits its cap. This guards against font-metric
            # surprises (HiDPI scaling, fallback fonts) making width_chars lie.
            if self.winfo_ismapped():
                for _ in range(3):
                    if self.winfo_reqwidth() <= self._cap_px + 60 or width_chars <= 24:
                        break
                    width_chars = max(24, int(width_chars * 0.8))
                    self._text.configure(width=width_chars)
                    self._text.update_idletasks()
            count = self._text.count("1.0", "end-1c", "displaylines")
            if count is None:
                return
            n = count[0] if isinstance(count, tuple) else int(count)
            # No max-height clamp: the bubble grows, the outer chat scrolls.
            self._text.configure(height=max(1, n))
        except Exception:
            pass

    def update_content(self, new_content: str):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if new_content == self.content:
            return
        self.content = new_content
        self._render_body(new_content)
        self._schedule_fit()


class ModernOllamaGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Ollama Studio")
        self.geometry("1100x720")
        self.minsize(850, 550)

        self.api = OllamaAPI("http://127.0.0.1:11434")
        self.chat_manager = ChatManager()
        self.is_generating = False
        self.stop_requested = False

        self._init_layout()
        self._refresh_models_async()

    def _init_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ------------------- SIDEBAR -------------------
        self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1)

        # Sidebar Title & New Chat
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="ew")

        ctk.CTkLabel(
            brand_frame, text="🦙 Ollama Studio", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        self.new_chat_btn = ctk.CTkButton(
            self.sidebar,
            text="+ New Chat",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1F6AA5",
            hover_color="#144870",
            command=self.on_new_chat,
        )
        self.new_chat_btn.grid(row=1, column=0, padx=15, pady=(5, 15), sticky="ew")

        # Chat History List Frame
        self.history_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.history_scroll.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")

        # Sidebar Bottom Settings & Controls
        sidebar_bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_bottom.grid(row=3, column=0, padx=15, pady=15, sticky="ew")

        # Appearance mode switch
        self.theme_option = ctk.CTkOptionMenu(
            sidebar_bottom,
            values=["Dark", "Light", "System"],
            command=self.change_appearance_mode_event,
            height=28,
        )
        self.theme_option.set("Dark")
        self.theme_option.pack(fill="x", pady=(0, 10))

        # Model Manager & Host Settings buttons
        manage_models_btn = ctk.CTkButton(
            sidebar_bottom,
            text="⚙️ Manage Models",
            fg_color="#2B2B2B",
            hover_color="#3B3B3B",
            command=self.open_model_management,
            height=30,
        )
        manage_models_btn.pack(fill="x", pady=(0, 5))

        # ------------------- MAIN CHAT AREA -------------------
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        # Header Bar
        header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(1, weight=1)

        # Model Selector
        ctk.CTkLabel(header, text="Model:", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, padx=(0, 8))
        self.model_selector = ctk.CTkOptionMenu(header, values=["Fetching models..."], width=180)
        self.model_selector.grid(row=0, column=1, sticky="w")

        # Host Input
        ctk.CTkLabel(header, text="Host:", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=2, padx=(15, 8))
        self.host_entry = ctk.CTkEntry(header, width=170)
        self.host_entry.insert(0, self.api.host)
        self.host_entry.grid(row=0, column=3, padx=(0, 10))
        self.host_entry.bind("<Return>", lambda e: self.update_host())

        # Parameters Button (System Prompt / Temp)
        param_btn = ctk.CTkButton(
            header, text="🎛️ Settings", width=90, fg_color="#333333", hover_color="#444444", command=self.open_chat_settings
        )
        param_btn.grid(row=0, column=4, padx=(0, 5))

        # Save / Load Chat Menu
        file_actions_btn = ctk.CTkButton(
            header, text="💾 Save/Load", width=90, fg_color="#333333", hover_color="#444444", command=self.open_file_menu
        )
        file_actions_btn.grid(row=0, column=5)

        # Scrollable Chat Container
        self.chat_display = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.chat_display.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.chat_display.grid_columnconfigure(0, weight=1)

        # Input Area Bar
        input_container = ctk.CTkFrame(self.main_container, corner_radius=15, border_width=1, border_color="#333333")
        input_container.grid(row=2, column=0, sticky="ew")
        input_container.grid_columnconfigure(0, weight=1)

        self.input_textbox = ctk.CTkTextbox(
            input_container, height=70, font=ctk.CTkFont(size=13), fg_color="transparent", activate_scrollbars=True
        )
        self.input_textbox.grid(row=0, column=0, padx=12, pady=8, sticky="ew")
        self.input_textbox.bind("<Shift-Return>", lambda e: None)
        self.input_textbox.bind("<Return>", self._on_enter_pressed)

        btn_container = ctk.CTkFrame(input_container, fg_color="transparent")
        btn_container.grid(row=0, column=1, padx=10, pady=8, sticky="se")

        self.send_btn = ctk.CTkButton(
            btn_container, text="Send ➔", width=70, height=36, fg_color="#1F6AA5", hover_color="#144870", command=self.on_send
        )
        self.send_btn.pack(side="right")

        self.stop_btn = ctk.CTkButton(
            btn_container, text="Stop 🛑", width=70, height=36, fg_color="#E53935", hover_color="#C62828", command=self.on_stop
        )

        self.refresh_history_ui()

    # ------------------- LOGIC & EVENTS -------------------
    def change_appearance_mode_event(self, new_mode: str):
        ctk.set_appearance_mode(new_mode)

    def update_host(self):
        new_host = self.host_entry.get().strip()
        if new_host:
            self.api.set_host(new_host)
            self._refresh_models_async()

    def _refresh_models_async(self):
        def _fetch():
            try:
                models = self.api.fetch_models()
            except Exception:
                models = ["Error: Host unreachable"]
            # Tkinter widgets must only be touched from the main thread.
            self.after(0, lambda: self._update_model_selector(models))

        threading.Thread(target=_fetch, daemon=True).start()

    def _update_model_selector(self, models: List[str]):
        if models and not models[0].startswith("Error"):
            self.model_selector.configure(values=models)
            self.model_selector.set(models[0])
        else:
            self.model_selector.configure(values=models if models else ["No models found"])
            self.model_selector.set(models[0] if models else "No models found")

    def refresh_sidebar(self):
        """Rebuild only the session list (cheap, no chat re-render)."""
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        active_id = self.chat_manager.active_session_id
        for session in self.chat_manager.sessions:
            is_active = session.id == active_id
            bg = "#1F6AA5" if is_active else "transparent"
            hover_bg = "#144870" if is_active else "#2B2B2B"

            btn_frame = ctk.CTkFrame(self.history_scroll, fg_color=bg, corner_radius=8)
            btn_frame.pack(fill="x", pady=3)
            btn_frame.grid_columnconfigure(0, weight=1)

            title_btn = ctk.CTkButton(
                btn_frame,
                text=session.title,
                anchor="w",
                fg_color="transparent",
                hover_color=hover_bg,
                command=lambda sid=session.id: self.switch_session(sid),
            )
            title_btn.grid(row=0, column=0, sticky="ew", padx=(2, 0))

            del_btn = ctk.CTkButton(
                btn_frame,
                text="✕",
                width=24,
                fg_color="transparent",
                hover_color="#C62828",
                text_color="#888888",
                command=lambda sid=session.id: self.delete_session(sid),
            )
            del_btn.grid(row=0, column=1, padx=(0, 4))

    def refresh_history_ui(self):
        self.refresh_sidebar()
        self.render_active_chat()

    def switch_session(self, session_id: str):
        if self.is_generating:
            return
        self.chat_manager.set_active_session(session_id)
        self.refresh_history_ui()

    def delete_session(self, session_id: str):
        if self.is_generating:
            return
        self.chat_manager.delete_session(session_id)
        self.refresh_history_ui()

    def on_new_chat(self):
        if self.is_generating:
            return
        self.chat_manager.create_new_session()
        self.refresh_history_ui()

    def _append_bubble(self, role: str, content: str) -> ChatBubble:
        """Append a single message row without rebuilding the whole chat."""
        row = ctk.CTkFrame(self.chat_display, fg_color="transparent")
        row.pack(fill="x", pady=3, padx=8)

        bubble = ChatBubble(row, role=role, content=content, on_copy=self.copy_text)
        if role == "user":
            bubble.pack(side="right", anchor="e", padx=(100, 2))
        else:
            bubble.pack(side="left", anchor="w", padx=(2, 100))

        # Keep bubbles capped to the chat width as the window resizes.
        row.bind("<Configure>", lambda e, b=bubble: b.adapt_width(e.width))
        try:
            bubble.adapt_width(max(300, self.chat_display.winfo_width() - 40))
        except Exception:
            pass
        return bubble

    def _is_near_bottom(self, threshold: float = 0.92) -> bool:
        try:
            _top, bottom = self.chat_display._parent_canvas.yview()
            return bottom >= threshold
        except Exception:
            return True

    def _scroll_to_bottom(self, force: bool = False):
        try:
            if force or self._is_near_bottom():
                self.chat_display._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def render_active_chat(self):
        for widget in self.chat_display.winfo_children():
            widget.destroy()

        session = self.chat_manager.get_active_session()
        visible = [m for m in session.messages if m["role"] in ("user", "assistant")]
        if not visible:
            empty = ctk.CTkLabel(
                self.chat_display,
                text="💬  Start a conversation\n\nPick a model above and type below.\nEnter to send · Shift+Enter for newline.",
                font=ctk.CTkFont(size=13),
                text_color="#777777",
                justify="center",
            )
            empty.pack(expand=True, pady=80)
            return

        for msg in visible:
            self._append_bubble(msg["role"], msg["content"])

        # Let layout settle, then jump to latest message
        self.after(50, lambda: self._scroll_to_bottom(force=True))

    def copy_text(self, text: str):
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)

    def _on_enter_pressed(self, event):
        if not (event.state & 0x1):  # Shift not pressed
            self.on_send()
            return "break"

    def on_send(self):
        if self.is_generating:
            return

        text = self.input_textbox.get("1.0", tk.END).strip()
        if not text:
            return

        selected_model = self.model_selector.get()
        if not selected_model or selected_model.startswith("Error") or selected_model == "No models found":
            messagebox.showerror("Error", "Please select or download a valid Ollama model first.", parent=self)
            return

        self.input_textbox.delete("1.0", tk.END)

        session = self.chat_manager.get_active_session()
        had_messages = len(session.messages) > 0
        session.add_message("user", text)
        # Only the sidebar title may have changed — don't rebuild chat bubbles.
        self.refresh_sidebar()
        if not had_messages:
            # First message replaces the empty-state placeholder.
            self.render_active_chat()
        else:
            self._append_bubble("user", text)
        self._scroll_to_bottom(force=True)

        # Disable input / toggle stop button
        self.is_generating = True
        self.stop_requested = False
        self.send_btn.pack_forget()
        self.stop_btn.pack(side="right")

        # Streaming placeholder bubble (reused for the whole response — no rebuilds)
        assistant_bubble = self._append_bubble("assistant", "● Thinking...")
        self._scroll_to_bottom(force=True)

        def _generate():
            full_response = ""
            last_flush = 0.0
            try:
                for chunk in self.api.chat_stream(
                    model=selected_model,
                    messages=session.messages,
                    system_prompt=session.system_prompt,
                    temperature=session.temperature,
                    stop_flag_callback=lambda: self.stop_requested,
                ):
                    full_response += chunk
                    # Throttle UI updates: at most ~1 per 60ms to avoid
                    # queueing hundreds of after() callbacks (was causing jank).
                    now = time.time()
                    if now - last_flush >= 0.06:
                        last_flush = now
                        snapshot = full_response
                        self.after(0, lambda res=snapshot: (
                            assistant_bubble.update_content(res),
                            self._scroll_to_bottom(),
                        ))

                if not full_response:
                    full_response = "[Stopped or empty response]"

                session.add_message("assistant", full_response)
                # Final flush with the complete text
                self.after(0, lambda res=full_response: (
                    assistant_bubble.update_content(res),
                    self._scroll_to_bottom(force=True),
                ))

            except Exception as e:
                err_msg = f"Error generation failed: {e}"
                session.add_message("assistant", err_msg)
                self.after(0, lambda: (
                    assistant_bubble.update_content(err_msg),
                    self._scroll_to_bottom(force=True),
                ))

            finally:
                self.after(0, self._finish_generation)

        threading.Thread(target=_generate, daemon=True).start()

    def on_stop(self):
        self.stop_requested = True

    def _finish_generation(self):
        self.is_generating = False
        self.stop_btn.pack_forget()
        self.send_btn.pack(side="right")
        # Intentionally only refresh the sidebar (session title may have
        # changed). Rebuilding all chat bubbles here was what made the
        # whole window appear to "refresh"/flicker on every response.
        self.refresh_sidebar()

    def open_model_management(self):
        ModelManagementDialog(self, self.api, on_models_updated=self._update_model_selector)

    def open_chat_settings(self):
        session = self.chat_manager.get_active_session()
        SettingsDialog(self, session, on_save_callback=self.render_active_chat)

    def open_file_menu(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Save / Load Session")
        dialog.geometry("300x160")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Chat Session Management", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=15)

        def _save():
            dialog.destroy()
            session = self.chat_manager.get_active_session()
            filepath = filedialog.asksaveasfilename(
                defaultextension=".json", filetypes=[("JSON files", "*.json")]
            )
            if filepath:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(session.to_dict(), f, indent=2)

        def _load():
            dialog.destroy()
            filepath = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
            if filepath:
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        session = ChatSession.from_dict(data)
                        self.chat_manager.sessions.insert(0, session)
                        self.chat_manager.active_session_id = session.id
                        self.refresh_history_ui()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load chat session: {e}")

        ctk.CTkButton(dialog, text="Save Current Chat", command=_save).pack(fill="x", padx=30, pady=5)
        ctk.CTkButton(dialog, text="Load Chat Session", command=_load, fg_color="#333333", hover_color="#555555").pack(fill="x", padx=30, pady=5)


def run():
    app = ModernOllamaGUI()
    app.mainloop()


if __name__ == "__main__":
    run()

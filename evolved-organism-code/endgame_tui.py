
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TextArea, Static
from textual.containers import Vertical
from pathlib import Path
import os

BASE = Path(os.environ.get("ENDGAME_BASE", "."))

class EndgameTUI(App):
    CSS = """
    #status { height: 6; border: solid green; }
    #editor { height: 1fr; border: solid cyan; }
    """
    BINDINGS = [("ctrl+q", "quit", "Quit"), ("ctrl+s", "save", "Save")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("ENDGAME-AI TUI | Ctrl+Q quit | Ctrl+S save | Type below", id="status")
        yield TextArea(id="editor")
        yield Footer()

    def action_save(self):
        ta = self.query_one("#editor", TextArea)
        (BASE / "tui_output.txt").write_text(ta.text, encoding="utf-8")
        self.query_one("#status", Static).update("Saved to tui_output.txt!")

if __name__ == "__main__":
    EndgameTUI().run()

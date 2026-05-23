"""Binary (hex-dump) viewer — the always-last fallback.

Registers with ``priority=-1`` and ``can_view = lambda _: True`` so
:meth:`ViewerRegistry.lookup` returns this spec only when no other
viewer claims the file.  The hex dump caps at the first
:data:`HEX_DUMP_BYTES` bytes; everything else is summarised in a
header line.

Pure stdlib — never throws, has no optional dependencies.  This is
also the safety net :class:`ViewerStack` falls back to when another
viewer's :meth:`load_path` raises.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from ..registry import ViewerSpec, register_viewer
from .base import FileViewer

#: How many bytes to show in the hex dump.  Anything beyond is
#: summarised; the cap keeps the QPlainTextEdit responsive.
HEX_DUMP_BYTES: int = 4096


class BinaryViewer(FileViewer):
    """Hex-dump preview for arbitrary files."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._editor = QPlainTextEdit(self)
        self._editor.setReadOnly(True)
        self._editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._editor.setFont(
            QFontDatabase.systemFont(QFontDatabase.FixedFont)
        )
        layout.addWidget(self._editor)

    # ------------------------------------------------------------------
    def load_path(self, path: Path) -> None:
        try:
            size = path.stat().st_size if path.is_file() else 0
        except OSError:
            size = 0
        header_parts = [f"{path.name}", f"{size:,} bytes"]
        try:
            header_parts.append(
                path.resolve().relative_to(Path.cwd()).as_posix()
            )
        except (ValueError, OSError):
            header_parts.append(str(path))
        header = "  •  ".join(header_parts)

        body = self._read_hex_dump(path)
        self._editor.setPlainText(f"{header}\n\n{body}")
        self.file_loaded.emit(path)

    def clear(self) -> None:
        self._editor.clear()

    # ------------------------------------------------------------------
    @staticmethod
    def _read_hex_dump(path: Path) -> str:
        if not path.is_file():
            return "(file not found)"
        try:
            with path.open("rb") as fp:
                data = fp.read(HEX_DUMP_BYTES + 1)
        except OSError as exc:
            return f"(could not read: {exc})"

        truncated = len(data) > HEX_DUMP_BYTES
        data = data[:HEX_DUMP_BYTES]

        lines = []
        for offset in range(0, len(data), 16):
            chunk = data[offset:offset + 16]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(
                chr(b) if 32 <= b < 127 else "." for b in chunk
            )
            lines.append(f"{offset:08x}  {hex_part:<47}  |{ascii_part}|")
        if truncated:
            lines.append("...")
            lines.append(f"(truncated to first {HEX_DUMP_BYTES} bytes)")
        return "\n".join(lines)


# Self-registration on import — binary always available, no deps.
register_viewer(ViewerSpec(
    key="binary",
    label="Binary",
    extensions=(),  # extension-less; matches via can_view fallback
    factory=BinaryViewer,
    can_view=lambda _path: True,
    priority=-1,  # always last
    description="Hex dump of the first 4 KB.  Universal fallback.",
))


__all__ = ["BinaryViewer", "HEX_DUMP_BYTES"]

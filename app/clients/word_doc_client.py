import asyncio
from pathlib import Path, PureWindowsPath
from uuid import uuid4

from docx import Document


class WordClient:
    OUTPUT_DIR = Path(__file__).resolve().parents[2] / "generated_documents"

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir if output_dir is not None else self.OUTPUT_DIR

    async def create_document(self, content: str, filename: str) -> dict:
        # python-docx and disk I/O are synchronous; keep them off the event loop.
        return await asyncio.to_thread(self._create_document, content, filename)

    def _create_document(self, content: str, filename: str) -> dict:
        if not content.strip():
            raise ValueError("Document content cannot be empty.")

        # Treat both slash styles as separators, including in Linux deployments.
        safe_filename = PureWindowsPath(filename).name
        if not safe_filename or any(char in safe_filename for char in '<>:"/\\|?*'):
            raise ValueError("Invalid document filename.")
        if not safe_filename.lower().endswith(".docx"):
            safe_filename = f"{safe_filename}.docx"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.output_dir / safe_filename
        document = Document()
        document.add_paragraph(content)

        # Exclusive creation prevents concurrent exports from overwriting files.
        while True:
            try:
                with file_path.open("xb") as output:
                    document.save(output)
                break
            except FileExistsError:
                file_path = self.output_dir / f"{Path(safe_filename).stem}_{uuid4().hex}.docx"

        return {"success": True, "filename": file_path.name, "path": str(file_path)}

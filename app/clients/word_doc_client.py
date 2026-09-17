from pathlib import Path
import asyncio
from uuid import uuid4

from docx import Document


class WordClient:

    OUTPUT_DIR = Path(__file__).resolve().parents[2] / "generated_documents"

    def __init__(self):

        self.OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

    async def create_document(
        self,
        content: str,
        filename: str,
    ) -> dict:

        # -----------------------------------------
        # Validate filename
        # -----------------------------------------

        if not content.strip():
            raise ValueError(
                "Document content cannot be empty."
            )

        if not filename.endswith(".docx"):
            filename = f"{filename}.docx"

        # -----------------------------------------
        # Prevent path traversal
        #
        # Example:
        #
        # ../../secret.docx
        #
        # should NOT be allowed.
        # -----------------------------------------

        safe_filename = f"{uuid4().hex}_{Path(filename).name}"

        file_path = self.OUTPUT_DIR / safe_filename

        # -----------------------------------------
        # Create Word document
        # -----------------------------------------

        document = Document()

        document.add_paragraph(content)

        # -----------------------------------------
        # Save document
        # -----------------------------------------

        await asyncio.to_thread(document.save, file_path)

        # -----------------------------------------
        # Return structured result
        # -----------------------------------------

        return {
            "success": True,
            "filename": safe_filename,
            "path": str(file_path),
        }

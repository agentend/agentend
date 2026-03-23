"""Document ingestion pipeline."""

from typing import Optional, List, Any
from dataclasses import dataclass
from enum import Enum
import logging

import httpx


logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Document types."""

    PDF = "pdf"
    IMAGE = "image"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


@dataclass
class DocumentChunk:
    """Single document chunk with embedding."""

    content: str
    metadata: dict[str, Any]
    embedding: Optional[List[float]] = None
    chunk_index: int = 0
    document_id: str = ""


@dataclass
class Document:
    """Document representation."""

    id: str
    source: str
    document_type: DocumentType
    content: str
    metadata: dict[str, Any]
    chunks: List[DocumentChunk] = None


class DocumentPipeline:
    """
    4-layer document ingestion pipeline.

    Layers: acquire -> transform -> classify -> chunk_and_embed
    """

    def __init__(
        self,
        embedding_model: Optional[str] = None,
        embedding_endpoint: Optional[str] = None,
    ):
        """
        Initialize document pipeline.

        Args:
            embedding_model: Model to use for embeddings (e.g., "sentence-transformers/all-MiniLM-L6-v2").
            embedding_endpoint: Optional endpoint for embedding service.
        """
        self.embedding_model = embedding_model or "sentence-transformers/all-MiniLM-L6-v2"
        self.embedding_endpoint = embedding_endpoint
        self.chunk_size = 512
        self.chunk_overlap = 50

    async def ingest(
        self,
        source: str,
        document_type: Optional[DocumentType] = None,
        metadata: Optional[dict] = None,
    ) -> Document:
        """
        Full ingestion pipeline.

        Args:
            source: File path or URL to document.
            document_type: Document type (auto-detected if None).
            metadata: Optional metadata.

        Returns:
            Processed document with chunks and embeddings.
        """
        metadata = metadata or {}

        # Layer 1: Acquire
        content = await self._acquire(source)
        logger.info(f"Acquired {len(content)} bytes from {source}")

        # Layer 2: Transform
        if document_type is None:
            document_type = self._detect_type(source)

        transformed = await self._transform(content, document_type)
        logger.info(f"Transformed to {document_type}")

        # Layer 3: Classify
        doc_classification = await self._classify(transformed)
        metadata["classification"] = doc_classification

        # Layer 4: Chunk and Embed
        chunks = await self._chunk_and_embed(transformed, metadata)
        logger.info(f"Created {len(chunks)} chunks with embeddings")

        doc = Document(
            id=self._generate_id(),
            source=source,
            document_type=document_type,
            content=transformed,
            metadata=metadata,
            chunks=chunks,
        )

        return doc

    async def _acquire(self, source: str) -> str:
        """
        Layer 1: Acquire document content.

        Args:
            source: File path or URL.

        Returns:
            Document content as string.
        """
        if source.startswith("http://") or source.startswith("https://"):
            # Fetch from URL
            async with httpx.AsyncClient() as client:
                response = await client.get(source, timeout=30.0)
                response.raise_for_status()
                return response.text
        else:
            # Read from file
            with open(source, "r", encoding="utf-8") as f:
                return f.read()

    async def _transform(self, content: str, doc_type: DocumentType) -> str:
        """
        Layer 2: Transform document to normalized format.

        Args:
            content: Raw content.
            doc_type: Document type.

        Returns:
            Normalized text content.
        """
        if doc_type == DocumentType.PDF:
            return await self._parse_pdf(content)
        elif doc_type == DocumentType.DOCX:
            return await self._parse_docx(content)
        elif doc_type == DocumentType.IMAGE:
            return await self._parse_image(content)
        elif doc_type == DocumentType.HTML:
            return await self._parse_html(content)
        else:
            # Plain text, markdown, JSON - return as-is
            return content

    async def _classify(self, content: str) -> dict[str, Any]:
        """
        Layer 3: Classify document type and extract metadata.

        Args:
            content: Document content.

        Returns:
            Classification metadata.
        """
        # Simple heuristic classification
        classification = {
            "category": "unknown",
            "language": "en",
            "has_code": "```" in content or "def " in content,
            "has_tables": "|" in content and "-" in content,
            "estimated_reading_time_minutes": len(content.split()) // 200,
        }

        if "import " in content or "function " in content or "class " in content:
            classification["category"] = "code"
        elif "def " in content or "async def" in content:
            classification["category"] = "python"
        elif "#" in content[:100]:
            classification["category"] = "markdown"
        else:
            classification["category"] = "text"

        return classification

    async def _chunk_and_embed(
        self,
        content: str,
        metadata: dict,
    ) -> List[DocumentChunk]:
        """
        Layer 4: Chunk content and generate embeddings.

        Args:
            content: Document content.
            metadata: Document metadata.

        Returns:
            List of chunks with embeddings.
        """
        # Split into chunks
        chunks = self._create_chunks(content)

        # Generate embeddings
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            try:
                embedding = await self._embed(chunk.content)
                chunk.embedding = embedding
            except Exception as e:
                logger.warning(f"Failed to embed chunk {i}: {e}")
                chunk.embedding = None

        return chunks

    def _create_chunks(self, content: str) -> List[DocumentChunk]:
        """
        Create overlapping chunks from content.

        Args:
            content: Document content.

        Returns:
            List of chunks.
        """
        chunks = []
        words = content.split()

        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i:i + self.chunk_size]
            if chunk_words:
                chunk_text = " ".join(chunk_words)
                chunk = DocumentChunk(
                    content=chunk_text,
                    metadata={
                        "word_count": len(chunk_words),
                    }
                )
                chunks.append(chunk)

        return chunks

    async def _embed(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.
        """
        if self.embedding_endpoint:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.embedding_endpoint,
                    json={"text": text, "model": self.embedding_model},
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("embedding", [])
        else:
            # Placeholder: would use actual embedding model
            # For now, return dummy embedding
            return [0.1] * 384

    async def _parse_pdf(self, content: str) -> str:
        """Parse PDF (placeholder)."""
        # In production, use PyPDF2 or pdfplumber
        return content

    async def _parse_docx(self, content: str) -> str:
        """Parse DOCX (placeholder)."""
        # In production, use python-docx
        return content

    async def _parse_image(self, content: str) -> str:
        """Parse image via OCR (placeholder)."""
        # In production, use Tesseract or cloud vision API
        return content

    async def _parse_html(self, content: str) -> str:
        """Parse HTML to plain text."""
        try:
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []

                def handle_data(self, data):
                    self.text.append(data)

            extractor = TextExtractor()
            extractor.feed(content)
            return " ".join(extractor.text)
        except Exception:
            return content

    def _detect_type(self, source: str) -> DocumentType:
        """Detect document type from source."""
        if source.endswith(".pdf"):
            return DocumentType.PDF
        elif source.endswith(".docx"):
            return DocumentType.DOCX
        elif source.endswith(".md"):
            return DocumentType.MARKDOWN
        elif source.endswith(".html") or source.endswith(".htm"):
            return DocumentType.HTML
        elif source.endswith(".json"):
            return DocumentType.JSON
        elif source.endswith((".png", ".jpg", ".jpeg", ".gif")):
            return DocumentType.IMAGE
        else:
            return DocumentType.TXT

    def _generate_id(self) -> str:
        """Generate document ID."""
        from uuid import uuid4
        return str(uuid4())

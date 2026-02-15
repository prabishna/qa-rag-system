from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from backend.config import settings
from backend.utils.milvus_client import milvus_client
from typing import List
import uuid
import logging
from datetime import datetime
from PIL import Image
import pytesseract
import io

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        # Initialize Semantic Chunking
        # This uses embeddings to identify semantic breakpoints
        embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.openai_api_key
        )
        
        self.text_splitter = SemanticChunker(
            embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=40.0
        )
    
    def extract_text_from_pdf(self, file_path: str) -> List[tuple]:
        """Extract text from PDF with position-aware OCR support using pdfplumber"""
        import pdfplumber
        
        pages = []
        
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                elements = []
                
                try:
                    # Extract text elements with positions
                    words = page.extract_words(
                        x_tolerance=3,
                        y_tolerance=3,
                        keep_blank_chars=False
                    )
                    
                    # Group words into lines based on Y position
                    lines = {}
                    for word in words:
                        y_pos = round(word['top'], 1)  # Round to group nearby words
                        if y_pos not in lines:
                            lines[y_pos] = []
                        lines[y_pos].append({
                            'text': word['text'],
                            'x': word['x0'],
                            'type': 'text'
                        })
                    
                    # Sort words in each line by X position (left to right)
                    for y_pos in lines:
                        lines[y_pos].sort(key=lambda w: w['x'])
                        # Join words into a line
                        line_text = ' '.join([w['text'] for w in lines[y_pos]])
                        elements.append({
                            'y': y_pos,
                            'type': 'text',
                            'content': line_text
                        })
                    
                    # Extract images with OCR
                    images = page.images
                    for img_idx, img in enumerate(images):
                        try:
                            # Get image bounding box
                            bbox = (img['x0'], img['top'], img['x1'], img['bottom'])
                            
                            # Crop and extract image
                            img_obj = page.within_bbox(bbox).to_image()
                            pil_image = img_obj.original
                            
                            # Perform OCR
                            ocr_text = pytesseract.image_to_string(pil_image)
                            
                            if ocr_text.strip():
                                elements.append({
                                    'y': img['top'],
                                    'type': 'image',
                                    'content': ocr_text.strip(),
                                    'name': f"Image_{page_num}_{img_idx}"
                                })
                                logger.info(f"OCR extracted {len(ocr_text)} chars from image at y={img['top']} on page {page_num}")
                        
                        except Exception as e:
                            logger.warning(f"OCR failed for image {img_idx} on page {page_num}: {e}")
                    
                    # Sort all elements by Y position (top to bottom)
                    elements.sort(key=lambda e: e['y'])
                    
                    # Build page content in reading order
                    page_content = []
                    for elem in elements:
                        if elem['type'] == 'text':
                            page_content.append(elem['content'])
                        else:  # image
                            page_content.append(f"\n[IMAGE: {elem['name']}]")
                            page_content.append(elem['content'])
                            page_content.append("[END IMAGE]\n")
                    
                    if page_content:
                        combined_text = '\n'.join(page_content)
                        pages.append((page_num, combined_text))
                
                except Exception as e:
                    logger.error(f"Failed to process page {page_num}: {e}")
                    # Fallback to basic text extraction
                    try:
                        text = page.extract_text()
                        if text and text.strip():
                            pages.append((page_num, text.strip()))
                    except:
                        logger.error(f"Fallback extraction also failed for page {page_num}")
        
        return pages
    
    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from text file (.txt, .md)"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def chunk_text(self, text: str, page_number: int = None) -> List[dict]:
        """Split text into chunks with semantic boundaries"""
        chunks = self.text_splitter.split_text(text)
        return [
            {"text": chunk, "page_number": page_number}
            for chunk in chunks
        ]
    
    def create_embedding(self, text: str) -> List[float]:
        """Create embedding using OpenAI"""
        response = self.openai_client.embeddings.create(
            model=settings.embedding_model,
            input=text
        )
        return response.data[0].embedding
    
    def process_document(self, file_path: str, filename: str) -> dict:
        """Main processing pipeline with metadata preservation"""
        document_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Extract text based on file type
        if filename.endswith('.pdf'):
            pages = self.extract_text_from_pdf(file_path)
            all_chunks = []
            for page_num, text in pages:
                chunks = self.chunk_text(text, page_num)
                all_chunks.extend(chunks)
        elif filename.endswith(('.txt', '.md')):
            text = self.extract_text_from_txt(file_path)
            all_chunks = self.chunk_text(text)
        else:
            raise ValueError(f"Unsupported file type: {filename}")
        
        if not all_chunks:
            raise ValueError(f"No text extracted from {filename}")
        
        # Create embeddings and prepare for Milvus
        milvus_data = {
            "chunk_id": [],
            "embedding": [],
            "document_id": [],
            "document_name": [],
            "chunk_text": [],
            "chunk_index": [],
            "page_number": []
        }
        
        for idx, chunk in enumerate(all_chunks):
            chunk_id = f"{document_id}_{idx}"
            embedding = self.create_embedding(chunk["text"])
            
            milvus_data["chunk_id"].append(chunk_id)
            milvus_data["embedding"].append(embedding)
            milvus_data["document_id"].append(document_id)
            milvus_data["document_name"].append(filename)
            milvus_data["chunk_text"].append(chunk["text"])
            milvus_data["chunk_index"].append(idx)
            milvus_data["page_number"].append(chunk.get("page_number") or 0)
        
        # Insert into Milvus
        milvus_client.insert_chunks(milvus_data)
        
        logger.info(f"Processed {filename}: {len(all_chunks)} chunks, timestamp: {timestamp}")
        
        return {
            "document_id": document_id,
            "filename": filename,
            "num_chunks": len(all_chunks),
            "status": "success",
            "message": "Document processed successfully",
            "timestamp": timestamp
        }

# Global instance
document_processor = DocumentProcessor()

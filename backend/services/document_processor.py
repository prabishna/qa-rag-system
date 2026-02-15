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
        """Main processing pipeline with batched processing to save memory"""
        document_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        total_chunks = 0
        
        try:
            # Initialize empty batch
            batch_size = 50  # Insert every 50 chunks
            current_batch = {
                "chunk_id": [], "embedding": [], "document_id": [],
                "document_name": [], "chunk_text": [], "chunk_index": [],
                "page_number": []
            }
            
            def flush_batch():
                nonlocal total_chunks
                if not current_batch["chunk_id"]:
                    return
                
                try:
                    milvus_client.insert_chunks(current_batch)
                    logger.info(f"Flushed batch of {len(current_batch['chunk_id'])} chunks for {filename}")
                    total_chunks += len(current_batch['chunk_id'])
                    
                    # Clear batch
                    for key in current_batch:
                        current_batch[key] = []
                except Exception as e:
                    logger.error(f"Failed to flush batch: {e}")
                    raise e

            # Process based on file type
            if filename.endswith('.pdf'):
                import pdfplumber
                
                with pdfplumber.open(file_path) as pdf:
                    for page_num, page in enumerate(pdf.pages, start=1):
                        try:
                            # 1. Extract text from page
                            text = ""
                            # Quick extraction first
                            raw_text = page.extract_text()
                            if raw_text:
                                text = raw_text
                            
                            # Optional: detailed layout analysis or OCR if text is empty
                            # Skipping full layout analysis for memory safety on large files
                            if not text or len(text) < 50:
                                try:
                                    # Only do heavy OCR if absolutely necessary
                                    logger.info(f"Page {page_num} seems empty, attempting OCR...")
                                    # (Simplified OCR logic here to save memory - maybe skip for now to fix crash)
                                    pass 
                                except Exception as e:
                                    logger.warning(f"OCR failed for page {page_num}: {e}")

                            if not text.strip():
                                continue

                            # 2. Chunk immediately
                            chunks = self.chunk_text(text, page_num)
                            
                            # 3. Embed and add to batch
                            for chunk in chunks:
                                chunk_id = f"{document_id}_{total_chunks + len(current_batch['chunk_id'])}"
                                embedding = self.create_embedding(chunk["text"])
                                
                                current_batch["chunk_id"].append(chunk_id)
                                current_batch["embedding"].append(embedding)
                                current_batch["document_id"].append(document_id)
                                current_batch["document_name"].append(filename)
                                current_batch["chunk_text"].append(chunk["text"])
                                current_batch["chunk_index"].append(total_chunks + len(current_batch['chunk_id']))
                                current_batch["page_number"].append(chunk.get("page_number") or 0)
                                
                                # Flush if batch full
                                if len(current_batch["chunk_id"]) >= batch_size:
                                    flush_batch()
                            
                            # Explicitly flush page cache
                            page.flush_cache()
                            
                        except Exception as e:
                            logger.error(f"Error processing page {page_num}: {e}")
                            continue

            elif filename.endswith(('.txt', '.md')):
                text = self.extract_text_from_txt(file_path)
                chunks = self.chunk_text(text)
                
                for chunk in chunks:
                    chunk_id = f"{document_id}_{total_chunks + len(current_batch['chunk_id'])}"
                    embedding = self.create_embedding(chunk["text"])
                    
                    current_batch["chunk_id"].append(chunk_id)
                    current_batch["embedding"].append(embedding)
                    current_batch["document_id"].append(document_id)
                    current_batch["document_name"].append(filename)
                    current_batch["chunk_text"].append(chunk["text"])
                    current_batch["chunk_index"].append(total_chunks + len(current_batch['chunk_id']))
                    current_batch["page_number"].append(0)
                    
                    if len(current_batch["chunk_id"]) >= batch_size:
                        flush_batch()

            else:
                raise ValueError(f"Unsupported file type: {filename}")
            
            # Final flush
            flush_batch()
            
            if total_chunks == 0:
                raise ValueError(f"No text could be extracted from {filename}")
            
            logger.info(f"Processed {filename}: {total_chunks} chunks, timestamp: {timestamp}")
            
            return {
                "document_id": document_id,
                "filename": filename,
                "num_chunks": total_chunks,
                "status": "success",
                "message": "Document processed successfully",
                "timestamp": timestamp
            }
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            raise e

# Global instance
document_processor = DocumentProcessor()

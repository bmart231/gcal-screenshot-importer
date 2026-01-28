"""
Google Cloud Vision OCR module
Handles text detection in images using Google Cloud Vision API.
"""

import os
from google.cloud import vision
from typing import Optional, Dict, List, Any
import io

class VisionOCR:
    """Wrapper for Google Cloud Vision API for OCR operations"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize the Vision API client
        Args:
            credentials_path: Path to the service account JSON file
            If None, uses GOOGLE_APPLICATION_CREDENTIALS env var
        """
        
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
        self.client: Any = vision.ImageAnnotatorClient()
    
    def extract_text(self, image_path: str) -> Dict[str, Any]:
        """
        Extract text from an image using Google Cloud Vision
        Args:
        image_path: Path to the image file  
        Returns:
            Dictionary containing:
                - full_text: Complete extracted text
                - blocks: List of text blocks with bounding boxes
                - confidence: Overall confidence score
        """
        # Read the image file
        with io.open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        
        # Perform text detection
        response = self.client.document_text_detection(image=image)
        
        if response.error.message:
            raise Exception(f'Vision API Error: {response.error.message}')
        
        # Extract full text
        full_text = response.full_text_annotation.text if response.full_text_annotation else ""
        
        # Extract text blocks with additional information
        blocks = []
        if response.full_text_annotation:
            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    block_text = ""
                    block_confidence = 0
                    
                    for paragraph in block.paragraphs:
                        para_text = ""
                        for word in paragraph.words:
                            word_text = "".join([symbol.text for symbol in word.symbols])
                            para_text += word_text + " "
                            block_confidence += word.confidence
                        
                        block_text += para_text.strip() + "\n"
                    
                    # Calculate average confidence for the block
                    num_words = sum(len(p.words) for p in block.paragraphs)
                    avg_confidence = block_confidence / num_words if num_words > 0 else 0
                    
                    blocks.append({
                        'text': block_text.strip(),
                        'confidence': avg_confidence,
                        'bounds': self._get_bounds(block.bounding_box)
                    })
        
        # Calculate overall confidence
        overall_confidence = sum(b['confidence'] for b in blocks) / len(blocks) if blocks else 0
        
        return {
            'full_text': full_text,
            'blocks': blocks,
            'confidence': overall_confidence
        }
    
    def extract_text_simple(self, image_path: str) -> str:
        """
        Extract just the text from an image (simplified version)
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text as a string
        """
        result = self.extract_text(image_path)
        return result['full_text']
    
    @staticmethod
    def _get_bounds(bounding_box):
        """Extract bounding box coordinates"""
        vertices = bounding_box.vertices
        return {
            'x_min': min(v.x for v in vertices),
            'y_min': min(v.y for v in vertices),
            'x_max': max(v.x for v in vertices),
            'y_max': max(v.y for v in vertices)
        }


def test_ocr(image_path: str):
    """Test function to verify OCR is working"""
    ocr = VisionOCR()
    result = ocr.extract_text(image_path)
    
    print("=== OCR Results ===")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"\nFull Text:\n{result['full_text']}")
    print(f"\nFound {len(result['blocks'])} text blocks")
    
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_ocr(sys.argv[1])
    else:
        print("Usage: python ocr.py <image_path>")
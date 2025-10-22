"""
Helper functions for gNB MCP Server
Contains utility functions for PDF processing, document extraction, and other helper operations.
"""

import re
import logging
from pathlib import Path
from typing import Optional, List, Tuple
import PyPDF2

logger = logging.getLogger(__name__)

def extract_pdf_toc(pdf_path: Path, keyword: str = "") -> str:
    """
    Extract table of contents from a PDF file, optionally filtered by keyword.
    
    Args:
        pdf_path: Path to PDF file
        keyword: Optional keyword to filter TOC entries
        
    Returns:
        Extracted TOC content, filtered if keyword is provided
    """
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Find the TOC pages
            toc_pages = []
            for i in range(min(20, len(pdf_reader.pages))):
                page_text = pdf_reader.pages[i].extract_text()
                if "Contents" in page_text:
                    # Found start of TOC
                    toc_pages.append(i)
                    # Add next several pages as they're likely part of TOC too
                    for j in range(i+1, min(i+10, len(pdf_reader.pages))):
                        toc_pages.append(j)
                    break
            
            if not toc_pages:
                return "Table of contents not found in document"
            
            # Extract text from TOC pages
            toc_text = ""
            for page_num in toc_pages:
                page_text = pdf_reader.pages[page_num].extract_text()
                
                # For first TOC page, start from "Contents"
                if page_num == toc_pages[0]:
                    contents_pos = page_text.find("Contents")
                    if contents_pos >= 0:
                        page_text = page_text[contents_pos:]
                
                # If we have a keyword, only include matching lines
                if keyword:
                    lines = page_text.split('\n')
                    matching_lines = [line for line in lines if keyword.lower() in line.lower()]
                    if matching_lines:
                        toc_text += f"\n--- PAGE {page_num+1} ---\n" + '\n'.join(matching_lines) + "\n\n"
                else:
                    toc_text += f"\n--- PAGE {page_num+1} ---\n{page_text}\n\n"
            
            return toc_text or f"No TOC entries found containing '{keyword}'"
            
    except Exception as e:
        return f"Error reading PDF TOC: {str(e)}"

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from a PDF file, focusing on content pages."""
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Get total number of pages
            total_pages = len(pdf_reader.pages)
            
            # Skip front matter - start from page 20 or 1/5 of document
            start_page = min(20, total_pages // 5)
            
            # Extract text from a reasonable number of content pages
            text = ""
            for i in range(start_page, min(start_page + 30, total_pages)):
                page_text = pdf_reader.pages[i].extract_text()
                text += f"\n--- PAGE {i+1} ---\n{page_text}\n\n"
            
            return text
    except ImportError:
        return "PDF extraction not available: PyPDF2 package is not installed"
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text content or error message
    """
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {e}")
        return f"Error reading PDF: {str(e)}"

def find_3gpp_document(knowledge_base_dir: Path, document: str) -> Tuple[Optional[Path], str]:
    """
    Find a 3GPP document PDF file in the knowledge base directory.
    
    Args:
        knowledge_base_dir: Path to the knowledge base directory
        document: 3GPP document number (e.g., "38.104", "38.211")
        
    Returns:
        Tuple of (pdf_file_path, error_message). If successful, error_message is empty.
    """
    if not knowledge_base_dir.exists():
        return None, f"Knowledge base directory not found: {knowledge_base_dir}"
    
    # Find matching PDF file
    doc_num = document.replace("TS ", "").replace(".", "")
    pdf_files = list(knowledge_base_dir.glob(f"*{doc_num}*.pdf"))
    
    if not pdf_files:
        available = [f.name for f in knowledge_base_dir.glob("*.pdf")]
        return None, f"Document TS {document} not found. Available: {available}"
    
    if len(pdf_files) > 1:
        return None, f"Multiple files found for TS {document}: {[f.name for f in pdf_files]}. Please be more specific."
    
    return pdf_files[0], ""

def extract_document_overview(full_text: str, document: str, pdf_file: Path) -> str:
    """
    Extract document overview from PDF text.
    
    Args:
        full_text: Full text content of the PDF
        document: Document number for display
        pdf_file: Path to the PDF file
        
    Returns:
        Formatted document overview
    """
    lines = full_text.split('\n')
    # Find first substantial content (skip headers, TOC, etc.)
    start_idx = 0
    for i, line in enumerate(lines[:500]):  # Check first 500 lines
        if len(line.strip()) > 50 and not re.search(r'\.{3,}|_{3,}|-{3,}', line):
            start_idx = i
            break
    
    preview = '\n'.join(lines[start_idx:start_idx + 100])
    return f"# TS {document}\n**File:** {pdf_file.name}\n\n{preview}\n\n*Specify section parameter for specific content*"

def extract_section_content(full_text: str, section: str, document: str, pdf_file: Path) -> str:
    """
    Extract specific section content from PDF text.
    
    Args:
        full_text: Full text content of the PDF
        section: Section number to extract (e.g., "5", "5.4", "5.4.3")
        document: Document number for display
        pdf_file: Path to the PDF file
        
    Returns:
        Formatted section content or error message
    """
    lines = full_text.split('\n')
    found_lines = []
    
    # Search for lines containing the section
    for i, line in enumerate(lines):
        # Look for exact section match at start of line
        if re.match(f"^\\s*{re.escape(section)}\\s+", line.strip()):
            # Found section start, collect content
            found_lines.append(f"=== SECTION {section} ===")
            
            # Add the section header line
            found_lines.append(line)
            
            # Add following lines until we hit another section or end
            for j in range(i + 1, min(i + 200, len(lines))):
                next_line = lines[j].strip()
                
                # Stop if we hit another major section
                if re.match(r'^\\d+(\\.\\d+)*\\s+[A-Za-z]', next_line) and j > i + 5:
                    break
                    
                # Skip obvious headers/footers
                if re.search(r'ETSI|3GPP|Release|Page \\d+|^\\d+\\s*$', next_line):
                    continue
                    
                found_lines.append(lines[j])
            
            break
    
    if not found_lines:
        # Fallback: search for any mention of the section
        for i, line in enumerate(lines):
            if section in line and len(line.strip()) > 10:
                found_lines.append(f"=== FOUND REFERENCE TO SECTION {section} ===")
                # Add context around the found line
                start = max(0, i - 5)
                end = min(len(lines), i + 50)
                for k in range(start, end):
                    found_lines.append(lines[k])
                break
    
    if not found_lines:
        return f"Error: Section {section} not found in TS {document}. Try a different section number or check document structure."
    
    result_text = '\n'.join(found_lines)
    
    # Limit size
    if len(result_text) > 6000:
        result_text = result_text[:6000] + "\n\n[Content truncated...]"
    
    return f"# TS {document} - Section {section}\n**File:** {pdf_file.name}\n\n{result_text}"

def list_available_3gpp_documents(knowledge_base_dir: Path) -> List[str]:
    """
    List all available 3GPP documents in the knowledge base directory.
    
    Args:
        knowledge_base_dir: Path to the knowledge base directory
        
    Returns:
        List of available document names
    """
    if not knowledge_base_dir.exists():
        return []
    
    pdf_files = list(knowledge_base_dir.glob("*.pdf"))
    return [f.name for f in pdf_files]

import re
import urllib.parse
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

class Chapter:
    def __init__(self, id: int, title: str, href: str, item_id: str = None):
        self.id = id
        self.title = title
        self.href = href
        self.item_id = item_id

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "href": self.href,
            "item_id": self.item_id
        }

class EPUBParser:
    """Parser EPUB tổng quát, hoạt động với mọi file EPUB."""
    
    def __init__(self, epub_path: str):
        self.epub_path = epub_path
        self.book = epub.read_epub(epub_path)
        
        metadata = self.book.get_metadata('DC', 'title')
        self.title = metadata[0][0] if metadata else "Unknown"
    
    def get_book_title(self) -> str:
        return self.title
        
    def _flatten_toc(self, toc):
        items = []
        for item in toc:
            if isinstance(item, epub.Link):
                items.append(item)
            elif isinstance(item, tuple):
                # tuple: (Section, [subitems])
                if isinstance(item[0], epub.Section):
                    items.append(item[0]) # Section acts as a Link too
                if len(item) > 1 and isinstance(item[1], list):
                    items.extend(self._flatten_toc(item[1]))
        return items
    
    def get_chapters(self) -> list[Chapter]:
        """Detect chapters theo 3 tầng ưu tiên."""
        chapters = []
        
        # Tầng 1: Thử dùng TOC
        if self.book.toc:
            flat_toc = self._flatten_toc(self.book.toc)
            if len(flat_toc) > 1:
                seen_hrefs = set()
                for item in flat_toc:
                    if not getattr(item, "href", None):  # Section không có link
                        continue
                    href = item.href.split('#')[0] # bỏ qua phần anchor nếu có
                    if href not in seen_hrefs:
                        seen_hrefs.add(href)
                        chapters.append(Chapter(
                            id=len(chapters),
                            title=item.title,
                            href=href
                        ))
                return chapters
        
        # Tầng 2 & 3: Fallback sang Spine và detect heading
        skip_patterns = ['cover', 'toc', 'nav', 'title', 'copyright']
        for item_id, _ in self.book.spine:
            item = self.book.get_item_with_id(item_id)
            if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
                
            name = item.get_name().lower()
            if any(skip in name for skip in skip_patterns):
                continue
            
            # Tầng 3: Thử detect heading trong file
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            heading = soup.find(['h1', 'h2', 'h3'])
            title = heading.get_text(strip=True) if heading else f"Chương {len(chapters)+1}"
            
            chapters.append(Chapter(
                id=len(chapters),
                title=title,
                href=item.get_name(),
                item_id=item_id
            ))
        
        return chapters
        
    def _find_item(self, href: str):
        """Tìm file theo href của mục lục; chịu được href mã hóa URL hoặc tương đối khác thư mục."""
        item = self.book.get_item_with_href(href)
        if item:
            return item
        plain = urllib.parse.unquote(href)
        item = self.book.get_item_with_href(plain)
        if item:
            return item
        tail = plain.lstrip('./').split('/')[-1]
        for it in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            if it.get_name().split('/')[-1] == tail:
                return it
        return None

    def get_chapter_paragraphs(self, chapter: Chapter) -> list[str]:
        """Trả về danh sách đoạn văn sạch của 1 chương"""
        if chapter.item_id:
            item = self.book.get_item_with_id(chapter.item_id)
        else:
            item = self._find_item(chapter.href)
            
        if not item:
            return []
            
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        for br in soup.find_all('br'):
            br.replace_with(' ')
        
        paragraphs = soup.find_all('p')
        if not paragraphs:
            text = soup.get_text(separator='\n')
            paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        else:
            # Không dùng get_text(strip=True): nó dính chữ khi đoạn có thẻ inline ("Hắn <i>nói</i>" -> "Hắnnói")
            texts = (' '.join(p.get_text().split()) for p in paragraphs)
            paragraphs = [t for t in texts if t]
            
        return paragraphs

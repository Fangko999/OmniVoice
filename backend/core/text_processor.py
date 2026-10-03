import re

class TextProcessor:
    """Xử lý văn bản tổng quát cho mọi loại truyện."""
    
    # Patterns phổ biến trong truyện dịch tiếng Việt
    ANNOTATION_PATTERNS = [
        r'\(\*[^)]*\)',          # (*...) 
        r'\[Dịch:[^\]]*\]',     # [Dịch:...]
        r'\[Chú[^\]]*\]',       # [Chú thích:...]
        r'\[TL:[^\]]*\]',       # [TL:...]
        r'\(Tên cũ[^)]*\)',     # (Tên cũ...)
    ]
    
    @classmethod
    def clean(cls, text: str) -> str:
        """Xóa chú thích, ký tự rác. Giữ nguyên nội dung truyện."""
        cleaned = text
        for pattern in cls.ANNOTATION_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned)
        
        # Xóa các dấu * đơn độc ở cuối hoặc trong văn bản (thường dùng cho đánh dấu chú thích)
        cleaned = cleaned.replace('*', '')
        
        # Chuyển các chữ cái viết hoa đứng một mình (như Y, A, O) thành chữ thường
        # để tránh việc AI nhận diện đây là từ viết tắt tiếng Anh và đọc thành "goai" (why), "ây" (a)
        cleaned = re.sub(r'\b([A-Z])\b', lambda m: m.group(1).lower(), cleaned)
        
        return cleaned.strip()
        
    @staticmethod
    def split_roles(text: str, narrator: str, dialogue: str) -> list[dict]:
        """Tách lời dẫn và lời thoại dựa trên ngoặc kép ("")"""
        
        if not text:
            return []

        # Chuẩn hóa ngoặc kép thông minh thành ngoặc kép thường
        text = text.replace('“', '"').replace('”', '"')

        # Tách đoạn văn thành các phần dựa trên dấu ngoặc kép ""
        # split('"') hoạt động tốt cả khi có xuống dòng bên trong ngoặc
        parts = text.split('"')
        
        segments = []
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
                
            if i % 2 == 1:
                # Chỉ số lẻ -> nằm trong ngoặc kép -> Lời thoại
                segments.append({
                    "voice": dialogue,
                    "text": part
                })
            else:
                # Chỉ số chẵn -> ngoài ngoặc kép -> Lời dẫn
                segments.append({
                    "voice": narrator,
                    "text": part
                })
                
        return segments

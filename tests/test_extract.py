import pdfplumber

def test_extract():
    pdf_path = "data/samples/1769543968773-7a7qa8q6s.pdf"
    
    print("--- pdfplumber column cropping text ---")
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        width = first_page.width
        height = first_page.height
        
        left_bbox = (0, 0, width / 2, height)
        right_bbox = (width / 2, 0, width, height)
        
        left_col = first_page.crop(left_bbox)
        right_col = first_page.crop(right_bbox)
        
        left_text = left_col.extract_text()
        right_text = right_col.extract_text()
        
        print("--- LEFT COLUMN ---")
        print(left_text[:500])
        print("...")
        print("--- RIGHT COLUMN ---")
        print(right_text[:500])
        print("...")

if __name__ == "__main__":
    test_extract()

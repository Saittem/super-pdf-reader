import fitz  # PyMuPDF

class PDFEngine:
    def __init__(self):
        self.doc = None
        self.filepath = ""

    def insert_custom_image(self, page_num, image_path, zoom):
        if not self.doc: return
        page = self.doc[page_num]
        
        # Define a default rectangle (e.g., top left, 100x100 points)
        # In a real app, you'd use mouse coordinates to place this
        rect = fitz.Rect(50, 50, 150, 150) 
        
        page.insert_image(rect, filename=image_path)

    def load_pdf(self, filepath):
        self.filepath = filepath
        self.doc = fitz.open(filepath)
        return len(self.doc)

    def get_page_image(self, page_num, zoom):
        if not self.doc or page_num < 0 or page_num >= len(self.doc):
            return None, 0, 0
        
        page = self.doc[page_num]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        # Convert to a format PyQt can read easily
        return pix.tobytes("ppm"), pix.width, pix.height

    def add_shape(self, page_num, shape_type, start_pt, end_pt, zoom):
        if not self.doc: return
        page = self.doc[page_num]
        
        # Un-scale the screen coordinates back to PDF coordinates
        x1, y1 = start_pt[0] / zoom, start_pt[1] / zoom
        x2, y2 = end_pt[0] / zoom, end_pt[1] / zoom
        
        # Create the rectangle and NORMALIZE IT to prevent the "infinite/empty" crash
        rect = fitz.Rect(x1, y1, x2, y2)
        rect.normalize() 

        if shape_type == "Rectangle":
            page.add_rect_annot(rect)
        elif shape_type == "Line":
            page.add_line_annot(fitz.Point(x1, y1), fitz.Point(x2, y2))
        elif shape_type == "Circle":
            page.add_circle_annot(rect)

    def add_pen_stroke(self, page_num, path_points, zoom):
        """Adds a freehand ink stroke to the PDF."""
        if not self.doc or len(path_points) < 2: return
        page = self.doc[page_num]
        
        # Ensure points are scaled and converted to fitz.Point objects
        pdf_points = [fitz.Point(p[0] / zoom, p[1] / zoom) for p in path_points]
        
        # The 'ink' annotation requires a list of 'strokes'
        # Even if we only have one continuous stroke, it must be inside a list: [stroke]
        page.add_ink_annot([pdf_points])

    def erase_annotation(self, page_num, pos, zoom):
        if not self.doc: return False
        page = self.doc[page_num]
        
        # Convert mouse click to PDF coordinates
        click_pt = fitz.Point(pos[0] / zoom, pos[1] / zoom)
        
        # Check all annotations on the page to see if we clicked one
        for annot in page.annots():
            if click_pt in annot.rect:
                page.delete_annot(annot)
                return True # Successfully erased
        return False

    def save_document(self):
        if self.doc:
            # Saves over the existing file
            self.doc.save(self.filepath, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
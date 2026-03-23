import fitz  # PyMuPDF


class PDFEngine:
    def __init__(self):
        self.doc = None
        self.filepath = ""

    def insert_custom_image(self, page_num, image_path, zoom):
        if not self.doc:
            return
        page = self.doc[page_num]
        # Default placement rect — in a full implementation you'd pass mouse coords here
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
        return pix.tobytes("ppm"), pix.width, pix.height

    def add_shape(self, page_num, shape_type, start_pt, end_pt, zoom):
        if not self.doc:
            return
        page = self.doc[page_num]

        x1, y1 = start_pt[0] / zoom, start_pt[1] / zoom
        x2, y2 = end_pt[0] / zoom, end_pt[1] / zoom

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
        if not self.doc or len(path_points) < 2:
            return
        page = self.doc[page_num]
        pdf_points = [(p[0] / zoom, p[1] / zoom) for p in path_points]
        page.add_ink_annot([pdf_points])

    def erase_annotation(self, page_num, pos, zoom):
        if not self.doc:
            return False
        page = self.doc[page_num]
        click_pt = fitz.Point(pos[0] / zoom, pos[1] / zoom)
        for annot in page.annots():
            if click_pt in annot.rect:
                page.delete_annot(annot)
                return True
        return False

    def save_document(self):
        """Save the document, falling back to a full rewrite if incremental save fails.
        
        FIX: incremental=True raises an exception on PDFs that were never cleanly saved
        (e.g. freshly created or repaired files). The fallback rewrites to a temp file
        and replaces the original, which is safe in all cases.
        """
        if not self.doc:
            return
        try:
            self.doc.save(
                self.filepath,
                incremental=True,
                encryption=fitz.PDF_ENCRYPT_KEEP
            )
        except Exception:
            # Fallback: full rewrite via a temporary file
            import os
            tmp_path = self.filepath + ".tmp"
            self.doc.save(tmp_path, garbage=4, deflate=True)
            self.doc.close()
            os.replace(tmp_path, self.filepath)
            self.doc = fitz.open(self.filepath)

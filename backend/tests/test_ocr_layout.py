from app.services.ocr import order_text_by_layout


def _box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def test_columns_are_read_as_separate_blocks():
    # Dua kolom berdampingan: urutan deteksi mentah mencampur kolom kiri dan kanan.
    items = [
        (_box(214, 43, 364, 64), "PT.INDOKARYA"),
        (_box(629, 39, 713, 53), "KERJA STABIL"),
        (_box(629, 54, 756, 68), "LINGKUNGAN MODERN"),
        (_box(214, 65, 371, 82), "GLOBAL SINERGI"),
    ]
    assert order_text_by_layout(items) == "PT.INDOKARYA\nGLOBAL SINERGI\n\nKERJA STABIL\nLINGKUNGAN MODERN"


def test_table_cells_keep_label_with_value_left_to_right():
    items = [
        (_box(130, 633, 219, 650), "SHIFT PAGI"),
        (_box(414, 633, 530, 650), "SHIFT MALAM"),
        (_box(63, 659, 317, 704), "Rp120.000"),
        (_box(342, 659, 585, 704), "Rp130.000"),
    ]
    assert order_text_by_layout(items) == "SHIFT PAGI\nRp120.000\n\nSHIFT MALAM\nRp130.000"


def test_boxes_on_the_same_line_are_joined_with_a_space():
    items = [
        (_box(100, 10, 160, 30), "Kirim"),
        (_box(170, 12, 220, 30), "CV"),
        (_box(100, 34, 300, 52), "0812-0000-0000"),
        (_box(5, 5, 6, 6), "x"),
    ]
    assert order_text_by_layout(items) == "Kirim CV\n0812-0000-0000"

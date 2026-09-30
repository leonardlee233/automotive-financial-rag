from src.chunking import chunk_text


def test_chunk_size_and_overlap():
    text = "第一句。" * 300
    chunks = list(chunk_text(text, size=800, overlap=120))
    assert len(chunks) >= 2
    assert all(1 <= len(chunk) <= 800 for chunk in chunks)
    assert chunks[0][-1] in "。！？；!?;"


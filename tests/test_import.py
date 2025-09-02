
def test_import():
    import paws3
    assert hasattr(paws3, "__version__")

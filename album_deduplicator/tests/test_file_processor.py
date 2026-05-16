from music_dup_lib.core.file_processor import _DummyPillowImage


def test_dummy_pillow_image_open_behaves_like_module_function():
    with _DummyPillowImage.open(object()) as image:
        assert isinstance(image, _DummyPillowImage)

"""Poster detail crops preserve source pixels and never introduce padding."""
import pytest
from PIL import Image
from add_borders import crop_to_square


def test_default_crop_is_backward_compatible():
    image = Image.effect_noise((160, 90), 50)
    assert crop_to_square(image).tobytes() == image.crop((35, 0, 125, 90)).tobytes()


def test_zoom_focus_selects_source_panel():
    image = Image.effect_noise((160, 90), 50)
    result = crop_to_square(image, zoom=2, focus=(0.5, 0.37))
    assert result.size == (45, 45)
    assert result.tobytes() == image.crop((58, 11, 103, 56)).tobytes()


def test_square_source_can_zoom_and_edge_crop_stays_inside():
    image = Image.new('RGB', (100, 100), 'red')
    result = crop_to_square(image, zoom=2, focus=(1, 0))
    assert result.size == (50, 50)
    assert result.getextrema() == ((255, 255), (0, 0), (0, 0))


@pytest.mark.parametrize('kwargs', [
    {'zoom': 0.5}, {'zoom': float('nan')}, {'zoom': float('inf')},
    {'focus': (-0.1, 0.5)}, {'focus': (0.5, float('nan'))},
    {'use_face_detection': True, 'focus': (0.2, 0.3)},
])
def test_invalid_crop_parameters(kwargs):
    with pytest.raises(ValueError):
        crop_to_square(Image.new('RGB', (100, 100)), **kwargs)

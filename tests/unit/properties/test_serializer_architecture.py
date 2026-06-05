"""Architecture guardrails for the split property serializer implementation."""

from pathlib import Path


def test_property_serializer_is_thin_public_facade():
    path = Path("usif/properties/serializer.py")
    text = path.read_text()
    assert len(text.splitlines()) < 160
    assert "usif.properties.serializers.dispatch" in text
    assert "class PropertySerializer" in text


def test_focused_serializer_modules_exist():
    root = Path("usif/properties/serializers")
    expected = {
        "common.py",
        "scalar.py",
        "vector.py",
        "tensor.py",
        "json_value.py",
        "numpy_value.py",
        "validation.py",
        "size.py",
        "dispatch.py",
        "__init__.py",
    }
    assert expected.issubset({path.name for path in root.glob("*.py")})


def test_serializer_facade_exports_stable_api():
    from usif.properties.serializer import PropertySerializer

    for name in ("serialize_value", "deserialize_value", "validate_value", "get_expected_size"):
        assert hasattr(PropertySerializer, name)

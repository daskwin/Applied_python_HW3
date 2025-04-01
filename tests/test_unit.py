import string
import pytest
from api.links import generate_short_code

def test_generate_short_code_length():
    code = generate_short_code()
    # Ожидаем, что длина сгенерированного кода равна 6 символам
    assert len(code) == 6

def test_generate_short_code_alphanumeric():
    code = generate_short_code()
    allowed_chars = string.ascii_letters + string.digits
    for char in code:
        assert char in allowed_chars
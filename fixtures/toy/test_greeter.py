from greeter import greet, hello


def test_hello():
    assert hello("Ada") == "hi Ada"


def test_greet():
    assert greet("Ada") == "hello, Ada!"

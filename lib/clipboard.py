import pyperclip


def read():
    return pyperclip.paste()


def write(text):
    pyperclip.copy(text)

# llmcwrapper/util.py
import sys


def color(code, s):
    return f"\x1b[{code}m{s}\x1b[0m"


def red(s):
    return color("31", s)


def green(s):
    return color("32", s)


def yellow(s):
    return color("33", s)


def blue(s):
    return color("34", s)


def info(s):
    print(s, file=sys.stderr)


def debug(s):
    print(s, file=sys.stderr)

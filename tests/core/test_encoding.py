from unittest import TestCase

from saku.core.encoding import byte_align_decode, byte_align_encode


class TestEncoding(TestCase):
    @staticmethod
    def test():
        for x in range(100000):
            assert x == next(byte_align_decode(byte_align_encode(x)))

        byte_str = b"".join(byte_align_encode(x) for x in range(100000))
        for i, n in enumerate(byte_align_decode(byte_str)):
            assert i == n

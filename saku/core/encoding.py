from typing import Iterator


def byte_align_encode(num: int) -> bytes:
    # Calculate no. of bits & bytes needed to repr int
    num_bits = num.bit_length()
    num_bytes = (num_bits + 6) // 7
    if num_bytes == 0:
        return b"\x00"

    encoded_bytes = bytearray(num_bytes)
    # Iterate through each byte and set the continuation bit if necessary
    for i in range(num_bytes - 1):
        # For other bytes, set the continuation bit to 1
        byte_val = num & 0x7F
        encoded_bytes[i] = byte_val | 0x80
        num >>= 7
    encoded_bytes[num_bytes - 1] = num & 0x7F
    return bytes(encoded_bytes)


def byte_align_decode(encoded_bytes: bytes) -> Iterator[int]:
    num = 0
    byte_ = 0
    byte_index = 0

    # Iterate through each byte in the encoded stream
    for byte_ in encoded_bytes:
        # Add the 7 least significant bits of the byte to the number
        num |= (byte_ & 0x7F) << (byte_index * 7)
        byte_index += 1

        # If the continuation bit is not set, return the number
        if not (byte_ & 0x80):
            yield num
            num = 0
            byte_index = 0

    # If the last byte had the continuation bit set, return an error
    if byte_ & 0x80:
        raise ValueError("Invalid byte alignment")

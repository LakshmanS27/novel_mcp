def luhn_check(number: str) -> bool:
    """
    Validates a credit/debit card number using the Luhn algorithm.
    """

    if not number.isdigit():
        return False

    total = 0
    reverse_digits = number[::-1]

    for i, digit in enumerate(reverse_digits):
        n = int(digit)

        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9

        total += n

    return total % 10 == 0


# Multiplication table
_d = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,2,3,4,0,6,7,8,9,5],
    [2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],
    [4,0,1,2,3,9,5,6,7,8],
    [5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],
    [7,6,5,9,8,2,1,0,4,3],
    [8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]

# Permutation table
_p = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,5,7,6,2,8,3,0,9,4],
    [5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],
    [9,4,5,3,1,2,6,8,7,0],
    [4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],
    [7,0,4,6,9,1,3,2,5,8],
]

# Inverse table
_inv = [0,4,3,2,1,5,6,7,8,9]


def verhoeff_check(number: str) -> bool:
    """
    Validates an Aadhaar number using the Verhoeff algorithm.
    """

    if not number.isdigit():
        return False

    c = 0

    reversed_digits = list(map(int, reversed(number)))

    for i, digit in enumerate(reversed_digits):
        c = _d[c][_p[i % 8][digit]]

    return c == 0
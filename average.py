from typing import Iterable

def average(numbers: Iterable[float]) -> float:
    """Return the arithmetic mean of `numbers`.

    Parameters
    ----------
    numbers : Iterable[float]
        A non-empty iterable of numbers.

    Returns
    -------
    float
        The arithmetic mean of all elements in `numbers`.

    Raises
    ------
    ValueError
        If `numbers` is empty.
    """
    numbers = list(numbers)
    if not numbers:
        raise ValueError("Cannot compute average of empty list")
    return sum(numbers) / len(numbers)

if __name__ == "__main__":
    data = [1, 2, 3, 4, 5]
    print("Average:", average(data))

def calculate_circle_emoji(count: int | float, total: int | float) -> str:
    """Return the appropriate circle percentage emoji based on the count and total.

    Rounds down to the nearest 10%
    """

    # Calculate the percentage rounded down to the nearest 10
    try:
        percentage = int(count / total * 10) * 10
    except ZeroDivisionError:
        raise ValueError("Total cannot be 0")

    if percentage > 100:
        percentage = 100

    return f":circle{percentage}:"

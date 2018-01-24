from math import gcd, ceil, floor

TU = 1024/1000000  # 1 TU = 1024 usec https://en.wikipedia.org/wiki/TU_(Time_Unit)
STD_BEACON_SCALE = 100
DEFAULT_START = STD_BEACON_SCALE/10
DEFAULT_END = STD_BEACON_SCALE*2

def coprime_rate_generator(start=DEFAULT_START, end=DEFAULT_END):
    """
    Generate a list of coprime rates that can be used as hop rates that minimize synchronization with standard beacon rate of 100TU
    
    :param target: The beacon rate to find alternative rates that are co-prime (no synchronization)
    :type target: int
    :param high_scaler: Multiplied by the target to set an upper limit
    :type high_scaler: float
    :return: List of coprimes
    :rtype: list
    """

    _results = {}
    # Generate an upper limit
    for i in range(floor(start), ceil(end)):
        if gcd(i, STD_BEACON_SCALE) == 1:
            _results[i] = round(i*TU, 5)

    return sorted(_results.items())


# Script can be run standalone
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a list of coprimes")
    parser.add_argument("start",
                        help="The start of the list to search for coprimes",
                        nargs='?',
                        type=float,
                        default=DEFAULT_START)
    parser.add_argument("end",
                        help="The end of the list to search for coprimes",
                        nargs='?',
                        type=float,
                        default=DEFAULT_END)
    arguments = parser.parse_args()

    print(coprime_rate_generator(arguments.start, arguments.end))

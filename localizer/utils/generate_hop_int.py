from math import gcd, ceil


TU = 1024/1000000  # 1 TU = 1024 usec https://en.wikipedia.org/wiki/TU_(Time_Unit)
STD_BEACON_INT = 100*TU
GENERATOR_SCALE = 10

def coprime_rate_generator(target=GENERATOR_SCALE, high_scaler=2):
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
    _limit = int(ceil(target*high_scaler))
    for i in range(_limit):
        if gcd(i, target) == 1:
            _results[i] = round(i*STD_BEACON_INT/GENERATOR_SCALE, 5)

    return sorted(_results.items())


# Script can be run standalone
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a list of coprimes")
    parser.add_argument("target",
                        help="The beacon rate to find alternative rates that are co-prime (no synchronization)",
                        nargs='?',
                        type=int,
                        default=10)
    parser.add_argument("scale",
                        help="Multiplied by the target to set an upper limit",
                        nargs='?',
                        default=2)
    arguments = parser.parse_args()

    print(coprime_rate_generator(arguments.target, arguments.scale))

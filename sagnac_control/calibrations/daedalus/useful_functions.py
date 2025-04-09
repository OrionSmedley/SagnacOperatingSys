import numpy as np

def range_increasing_directional(min, max, step=1):
    """
    A range-like function which
    1. includes the endpoint
    2. returns elements in the ragne in the order:
    zero, if in array
    positive values from smallest to largest
    zero, if in array
    negative values from smallest to largest (in magnitude)
    """

    if min > max:
        temp = min
        min = max
        max = temp
    rng = np.arange(min, max, np.abs(step))
    if max not in rng:
        rng = np.append(rng, max)

    srange = []
    pos = rng[rng>0]
    neg = rng[rng<0]
    if pos.size > 0:
        if 0 in rng:
            srange.append([0])
        srange.append(pos)
    if neg.size > 0:
        if 0 in rng:
            srange.append([0])
        srange.append(neg[::-1]) # put into right order

    return np.concatenate(srange)

def range_decreasing_directional(min, max, step=1):
    """
    A range-like function which
    1. includes the endpoint
    2. returns elements in the ragne in the order:
    positive values from largest to smallest
    negative values from largest to smallest (in magnitude)
    """
    if min > max:
        temp = min
        min = max
        max = temp
    rng = np.arange(min, max, np.abs(step))
    if max not in rng:
        rng = np.append(rng, max)

    srange = []
    pos = rng[rng>0]
    neg = rng[rng<0]
    if pos.size > 0:
        srange.append(pos[::-1]) # put into right order
    if neg.size > 0:
        srange.append(neg)

    return np.concatenate(srange)

def range_hysteresis(min, max, step=1):
    """
    range-like function which
    1. includes the endpoint
    2. returns elements in the order:
    min to max
    max to min
    """
    if min > max:
        temp = min
        min = max
        max = temp
    rng = np.arange(min, max, np.abs(step))
    if max not in rng:
        rng = np.append(rng, max)

    return np.append(rng, rng[::-1])

def range_zigzag(min, max, step=1):
    """
    range-like function which
    1. includes the endpoint
    2. returns elements in the order:
    0 to max
    max to min
    min to max
    """
    assert min < 0, "Minimum must be negative!"
    assert max > 0, "Maximum must be positive!"
    rng = np.arange(min, max, np.abs(step))
    if max not in rng:
        rng = np.append(rng, max)

    srange = []
    if 0. not in rng:
        srange.append([0])

    srange.append(rng[rng>0])
    srange.append(rng[::-1])
    srange.append(rng[rng<0])
    if 0. not in rng:
        srange.append([0])

    return np.concatenate(srange)

async def generate_lottery_numbers():
    import random

    nums = set()
    while len(nums) < 7:
        nums.add(random.randint(1, 49))
    return list(nums)

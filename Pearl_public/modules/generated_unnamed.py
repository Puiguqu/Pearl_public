import asyncio

async def count_up_to_ten():
    count = 0
    while count < 10:
        await asyncio.sleep(1)
        print(count)
        count += 1

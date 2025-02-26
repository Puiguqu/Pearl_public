import asyncio

async def count_to_10():
    for i in range(1, 11):
        await asyncio.sleep(1)
        print(i)

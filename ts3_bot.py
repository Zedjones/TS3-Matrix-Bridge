import asyncio

URI = "telnet://zedjones:PASSWORD@ts.traphouse.us:25639"

async def async_print(text):
    print(text)

async def async_test():
    await asyncio.sleep(5)
    print('tested')

def main():
    loop = asyncio.get_event_loop()
    lst_of_tasks = [
        async_print('start'),
        async_test(),
        async_print('end')
    ]
    loop.run_until_complete(asyncio.wait(lst_of_tasks))

if __name__ == '__main__':
    main()
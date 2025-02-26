import asyncio
import logging

# Assume execute_command is defined elsewhere (or see the previous example)
# from command_executor import execute_command

# For demonstration, here is a dummy execute_command function.
# In your actual code, this should call your dynamic executor (e.g., using execute_function).
async def execute_command(command: str, *args, **kwargs):
    logging.info(f"Executing command: {command}")
    # Here you would parse and execute the command.
    # For now, we simulate execution by returning a dummy result.
    await asyncio.sleep(1)
    return f"Result for {command}"

# Create an asyncio queue for command strings.
command_queue = asyncio.Queue()

async def function_executor():
    """
    Continuously check for new commands in the command queue and execute them.
    Each command is expected to be a string in the format:
        "execute:module_name.function_name"
    """
    logging.info("Function Executor started.")
    while True:
        if not command_queue.empty():
            command = await command_queue.get()
            logging.info(f"Function Executor: Received command: {command}")
            try:
                # Execute the command.
                result = await execute_command(command)
                logging.info(f"Function Executor: Command '{command}' executed with result: {result}")
            except Exception as e:
                logging.error(f"Function Executor: Error executing command '{command}': {e}")
            finally:
                command_queue.task_done()
        await asyncio.sleep(1)  # Add a small delay to prevent tight loop

# Example usage
if __name__ == "__main__":
    async def main():
        # Add some commands to the queue for testing
        await command_queue.put("execute:module.function1")
        await command_queue.put("execute:module.function2")
        
        # Start the function executor
        await function_executor()

    asyncio.run(main())

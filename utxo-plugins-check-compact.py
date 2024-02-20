import docker
import re
import subprocess
import time


def extract_latest_flush_number(logs):
    pattern = r'INFO:Database:flush #([\d,]+)'
    matches = re.findall(pattern, logs)
    if matches:
        flush_count_str = matches[-1].replace(',', '')
        return int(flush_count_str)
    else:
        return None


def get_utxo_plugin_containers():
    client = docker.from_env()
    return [container for container in client.containers.list(all=True) if "utxo-plugin" in container.name]


def print_container_info(container, flush_count):
    coin_name = container.name.split('-')[-2]
    print(f"Container: {container.name}, Coin: {coin_name}, Flush Count: {flush_count}")


def stop_and_compact(container):
    coin_name = container.name.split('-')[-2]
    container.stop(timeout=60 * 10)
    print(f"Executing docker-compose for utxo-plugin-{coin_name}")

    # Start the docker-compose command
    command = ['docker-compose', '--env-file', '.env', 'run', '-e', 'SKIP_COMPACT=false', '--rm',
               f'utxo-plugin-{coin_name}']

    # Run the docker-compose command
    process = subprocess.Popen(command)
    print("Subprocess started")

    # Wait for the container to be created
    print("Waiting for the container to be created...")
    time.sleep(10)  # Adjust the sleep duration as needed

    # Connect to Docker daemon
    client = docker.from_env()

    # Find the newly created container
    print("Searching for the newly created container...")
    new_container = None
    for c in client.containers.list():
        if f"utxo-plugin-{coin_name}" in c.name:
            new_container = c
            print("Newly created container found:")
            print(f"Container ID: {new_container.id}, Name: {new_container.name}")
            break

    if new_container:
        # Get logs from the newly created container
        print("Retrieving logs from the newly created container...")
        logs = new_container.logs().decode('utf-8')

        # Monitor the logs until the desired log line appears
        print("Monitoring logs from the newly created container:")
        while "[utxoplugin] History compaction complete" not in logs:
            try:
                if not client.containers.get(new_container.id):
                    print("Container no longer exists. Exiting monitoring loop.")
                    break
                else:
                    logs = new_container.logs().decode('utf-8')
            except docker.errors.NotFound:
                print("Container not found. Exiting monitoring loop.")
                break
            time.sleep(1)  # Wait for 10 seconds before retrying

        print(f"History compaction complete. Terminating {new_container.name}")
        try:
            # Terminate the subprocess
            new_container.stop(timeout=60 * 10)
            # process.terminate()
            # process.wait(timeout=60*10)
            print(f"{new_container.name} terminated successfully.")
        except Exception as e:
            print(f"Error terminating {new_container.name}: {e}")

        time.sleep(10)
        # Start the original container again
        print(f"Starting container {container.name}")
        container.start()
    else:
        print("Newly created container not found.")


def main():
    flush_count_threshold = 60000
    containers = get_utxo_plugin_containers()
    for container in containers:
        # try:
        logs = container.logs().decode('utf-8')
        flush_count = extract_latest_flush_number(logs)
        print_container_info(container, flush_count)
        # if container.name.split('-')[-2] == "BLOCK":
        if flush_count and flush_count > flush_count_threshold:
            print(f"Stopping container {container.name} as flush count {flush_count} exceeds threshold")
            stop_and_compact(container)
        # except Exception as e:
        #     print(f"Error processing container {container.name}: {str(e)}")


if __name__ == "__main__":
    main()

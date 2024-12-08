import docker
import re
import subprocess
import time
from datetime import datetime

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
    container.stop(timeout=60 * 10)  # Stop the container with a timeout of 10 minutes

    # Check if the container is stopped
    container.reload()
    if container.status != 'exited':
        raise RuntimeError(f"Failed to stop container {container.name} within the timeout period.")

    # Container has stopped, continue with further actions
    print(f"Container {container.name} stopped successfully.")

    print(f"Executing docker-compose for utxo-plugin-{coin_name} compaction")

    command = ['docker-compose', '--env-file', '.env', 'run', '-e', 'SKIP_COMPACT=false', '--rm',
               f'utxo-plugin-{coin_name}']
    process = subprocess.Popen(command)
    print("Subprocess started")

    print("Waiting for the container to be created...")
    # Initialize Docker client
    client = docker.from_env()
    # Timeout settings
    timeout = 120  # 2 minutes
    interval = 5  # Check every 5 seconds
    elapsed_time = 0
    new_container = None
    while elapsed_time < timeout:
        print(f"Checking for the newly created container (Elapsed time: {elapsed_time}s)...")
        for c in client.containers.list():
            if f"utxo-plugin-{coin_name}" in c.name and "run" in c.name:
                new_container = c
                print("Newly created container found:")
                print(f"Container ID: {new_container.id}, Name: {new_container.name}")
                break
        if new_container:
            break
        time.sleep(interval)
        elapsed_time += interval

    if new_container:
        print("Retrieving logs from the newly created container...")
        logs = new_container.logs().decode('utf-8')

        print("Monitoring logs from the newly created container:")
        while "[utxoplugin] History compaction complete" not in logs:
            try:
                if not client.containers.get(new_container.id):
                    print("Container no longer exists. Exiting monitoring loop.")
                    break
                else:
                    buff = new_container.logs().decode('utf-8')
                    logs = buff
            except (docker.errors.NotFound, docker.errors.APIError):
                print("Container not found. Exiting monitoring loop.")
                break
            time.sleep(1)

        print(f"History compaction complete. Terminating {new_container.name}")
        try:
            new_container.stop(timeout=60 * 10)
            new_container.reload()
            if new_container.status != 'removing':
                raise RuntimeError(f"Failed to stop container {new_container.name} within the timeout period.")

            print(f"{new_container.name} terminated successfully.")
        except Exception as e:
            print(f"Error terminating {new_container.name}: {e}")

        time.sleep(10)
        print(f"Starting container {container.name}")
        container.start()
    else:
        print("Newly created container not found.")


def main():
    flush_count_threshold = 60000
    containers = get_utxo_plugin_containers()
    for container in containers:
        logs = container.logs().decode('utf-8')
        flush_count = extract_latest_flush_number(logs)
        print_container_info(container, flush_count)
        if flush_count and flush_count > flush_count_threshold:
            print(f"Stopping container {container.name} as flush count {flush_count} exceeds threshold")
            stop_and_compact(container)


if __name__ == "__main__":
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    main()

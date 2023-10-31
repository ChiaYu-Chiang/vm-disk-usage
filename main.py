import paramiko
import json
import time


def remote_vm_command(ip, port, user, pwd, command, encoding):
    print(f"Connecting to {ip}...")
    try:
        ssh.connect(ip, username=user, port=port, password=pwd)
        print("Connected successfully.")
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)
        output = ssh_stdout.read().decode(encoding)
        print(output)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    starttime = time.time()

    with open("targets.json") as json_file:
        targets = json.load(json_file)

    linux_command = "df -h"
    windows_command = 'powershell -Command "Get-Volume"'

    print("Initializing SSHClient...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("SSHClient initialized.")

    for target in targets:
        if target["os"] == "linux":
            remote_vm_command(
                target["ip"],
                target["port"],
                target["user"],
                target["pwd"],
                linux_command,
                encoding="utf-8",
            )
        elif target["os"] == "windows":
            remote_vm_command(
                target["ip"],
                target["port"],
                target["user"],
                target["pwd"],
                windows_command,
                encoding="cp950",
            )
        else:
            pass
    print("Closing SSHClient...")
    ssh.close()
    print("SSHClient closed.")

    endtime = time.time()
    deltatime = endtime - starttime
    print(f"time used: {deltatime}s")

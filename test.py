import json
import time
from ssh_utils import SSHClient
from parser_utils import parse_linux_output, parse_windows_output


if __name__ == "__main__":
    starttime = time.time()

    target_percent = 80
    high_usage_ips = []

    with open("targets.json") as json_file:
        targets = json.load(json_file)

    ssh = SSHClient()

    command_and_parser = {
        "linux": ("df /", parse_linux_output),
        "windows": (
            'powershell -Command "Get-CimInstance -ClassName Win32_logicalDisk -Filter "DriveType=3" | Select-Object -Property DeviceID, Size, FreeSpace | Format-Table -AutoSize"',
            parse_windows_output,
        ),
    }

    for target in targets:
        ssh.connect(target["ip"], target["port"], target["user"], target["pwd"])
        command, parser = command_and_parser.get(target["os"], (None, None))
        if command and parser:
            output = ssh.execute_command(
                command, "utf-8" if target["os"] == "linux" else "cp950"
            )

            linux_fake_output = """
            Filesystem     1K-blocks    Used Available Use% Mounted on
            /dev/sda1       15481840 15117368   9940880  34% /
            """
            windows_fake_output = """
            DeviceID         Size   FreeSpace
            --------         ----   ---------
            C:           1000000000    100000000
            D:           2000000000    100000000
            E:           3000000000    100000000
            """
            fake_output = (
                linux_fake_output if target["os"] == "linux" else windows_fake_output
            )
            usages = parser(fake_output)
            for usage in usages:
                if usage >= target_percent and target["ip"] not in high_usage_ips:
                    high_usage_ips.append(target["ip"])
            print(f"ip: {target['ip']}, usage: {usages}%")

    if high_usage_ips:
        print(f"檢測到高於磁碟使用率 {target_percent}% 的VM IP:")
        for ip in high_usage_ips:
            print(ip)
    else:
        print(f"未檢測到高於磁碟使用率 {target_percent}% 的VM")

    ssh.close()

    endtime = time.time()
    deltatime = endtime - starttime
    print(f"time used: {round(deltatime, 1)}s")

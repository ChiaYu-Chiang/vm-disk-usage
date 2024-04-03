import json
import time
from ssh_utils import SSHClient
from parser_utils import parse_linux_output, parse_windows_output
from sendmail import send_email


if __name__ == "__main__":
    starttime = time.time()

    target_percent = 80
    scanned_vms = []
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
        try:
            ssh.connect(target["ip"], target["port"], target["user"], target["pwd"])
        except Exception as e:
            print(f"Error connecting to {target['ip']}: {e}")
            continue
        command, parser = command_and_parser.get(target["os"], (None, None))
        if command and parser:
            output = ssh.execute_command(
                command, "utf-8" if target["os"] == "linux" else "cp950"
            )
            if output is not None:
                usages = parser(output)
                for usage in usages:
                    if usage >= target_percent and target["ip"] not in high_usage_ips:
                        high_usage_ips.append(target["ip"])
                    scanned_vms.append((target["ip"], target["name"]))
                print(f"ip: {target['ip']}, usage: {usages}%")
        ssh.close()
    
    if high_usage_ips:
        email_body = f"<span style='color: red;'>檢測到高於磁碟使用率 {target_percent}% 的VM IP:<br>"
        for ip in high_usage_ips:
            print(ip)
            email_body += ip + "<br>"
    else:
        email_body = f"<span style='color: green;'>未檢測到高於磁碟使用率 {target_percent}% 的VM<br>"
    print(email_body)

    if scanned_vms:
        email_body += f"</span>已掃描VM:<br>"
        for vm in scanned_vms:
            print(vm)
            print(vm[0])
            email_body += f"{vm[0]} {vm[1]}<br>"

    subject = "高磁碟使用率通知"
    to_email = "brian_chiang@chief.com.tw, marco_li@chief.com.tw, aaron_lin@chief.com.tw, allen_yang@chief.com.tw"
    send_email(subject, email_body, to_email)

    endtime = time.time()
    deltatime = endtime - starttime
    print(f"time used: {round(deltatime, 1)}s")

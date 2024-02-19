def parse_linux_output(output):
    lines = output.strip().split("\n")
    data_line = lines[1]
    total_space = int(data_line.split()[1])
    used_space = int(data_line.split()[2])
    usage_percent = round((used_space / total_space) * 100, 1)
    return [usage_percent]


def parse_windows_output(output):
    lines = output.strip().split("\n")
    data_line = lines[2:]
    usages = []
    for line in data_line:
        data = line.split()
        free_space = int(data[2])
        total_space = int(data[1])
        used_space = total_space - free_space
        usage_percent = round((used_space / total_space) * 100, 1)
        usages.append(usage_percent)
    return usages


# 在主程式中測試 Linux 輸出
linux_output = """
Filesystem     1K-blocks    Used Available Use% Mounted on
/dev/sda1        2000000 1000000    900000  50% /
"""
linux_usages = parse_linux_output(linux_output)
print(linux_usages)  # 應該輸出 [50.0]

# 在主程式中測試 Windows 輸出
windows_output = """
DeviceID         Size   FreeSpace
--------         ----   ---------
C:       106796412928 66590281728
D:       100000000000 20000000000
E:       100000000000 15000000000
"""
windows_usages = parse_windows_output(windows_output)
print(windows_usages)  # 應該輸出 [37.8, 85.0, 85.0]

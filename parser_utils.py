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

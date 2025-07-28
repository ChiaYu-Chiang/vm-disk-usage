import json
import time
from ssh_utils import SSHClient
import socket, paramiko
import re
import pyodbc

def convert_to_mb(size_str):
    """
    將各種單位的大小字符串轉換為MB整數
    例如: "1G" -> 1024, "500M" -> 500, "1T" -> 1048576
    """
    size_str = size_str.strip()
    if not size_str or size_str == '-':
        return 0
        
    # 處理百分比
    if size_str.endswith('%'):
        try:
            return float(size_str.rstrip('%'))
        except ValueError:
            return 0
            
    # 統一格式化，確保數字和單位間沒有空格
    size_str = size_str.replace(' ', '')
    
    # 提取數字和單位
    match = re.match(r'^([\d.]+)([KMGTB]?).*', size_str, re.IGNORECASE)
    if not match:
        try:
            return float(size_str)  # 嘗試直接轉換為數字
        except ValueError:
            return 0
            
    value, unit = match.groups()
    try:
        value = float(value)
    except ValueError:
        return 0
        
    # 單位轉換到MB
    unit = unit.upper()
    if unit == 'K':
        return value / 1024
    elif unit == 'M':
        return value
    elif unit == 'G':
        return value * 1024
    elif unit == 'T':
        return value * 1024 * 1024
    elif unit == 'B':
        return value / (1024 * 1024)
    else:  # 沒有單位，假設為B
        return value / (1024 * 1024)

def get_linux_disk_usage(ssh):
    """
    獲取Linux系統中所有實際掛載硬碟的使用量詳細資訊
    1. 使用lsblk獲取磁碟結構
    2. 使用df獲取使用量數據
    3. 返回每顆硬碟的用量詳細資訊
    """
    # 取得磁碟結構，包含LVM
    # 使用更詳細的lsblk命令，包含KNAME (kernel device name)
    lsblk_cmd = "lsblk -o NAME,KNAME,TYPE,SIZE,MOUNTPOINT -n -p"
    lsblk_output = ssh.execute_command(lsblk_cmd, "utf-8")

    if not lsblk_output:
        return {}
   
    # 解析lsblk輸出，找出所有實際掛載點
    physical_disks = {}  # 記錄物理磁碟資訊
    logical_volumes = {}  # 記錄邏輯捲軸和分割區資訊
    
    # 保存磁碟hierarchical關係的字典
    disk_hierarchy = {}  # key: 設備路徑, value: 父設備路徑
   
    lines = lsblk_output.strip().split('\n')
    current_path = []  # 堆疊用來追蹤層級關係
    prev_indent = -1
    
    # 為了debug打印原始輸出
    """
    print("\n原始lsblk輸出:")
    print(lsblk_output)
    """

    for line in lines:
        # 計算縮排級別
        indent = 0
        original_line = line
        
        while line.startswith('├─') or line.startswith('└─') or line.startswith('│ '):
            line = line[2:]
            indent += 1
            
        line = line.strip()
        parts = line.split()
        
        if not parts:
            continue
            
        device_path = parts[0]
        kname = parts[1] if len(parts) > 1 else device_path  # 獲取kernel name
        device_type = parts[2] if len(parts) > 2 else ""
        device_size = parts[3] if len(parts) > 3 else ""
        mount_point = parts[4] if len(parts) > 4 else None
        
        # 管理層級關係
        if indent == 0:  # 根層級 (物理磁碟)
            current_path = [device_path]
        elif indent > prev_indent:  # 進入更深層級
            current_path.append(device_path)
        elif indent == prev_indent:  # 同一層級
            current_path.pop()
            current_path.append(device_path)
        else:  # 返回較淺層級
            while len(current_path) > indent:
                current_path.pop()
            current_path.append(device_path)
        
        prev_indent = indent
        
        # 記錄父子關係
        if len(current_path) > 1:
            parent = current_path[-2]
            disk_hierarchy[device_path] = parent
        
        # 記錄物理磁碟資訊
        if device_type == 'disk':
            physical_disks[device_path] = {
                'size': device_size,
                'size_mb': convert_to_mb(device_size),
                'partitions': [],
                'type': 'disk',
                'mount_points': []
            }
        
        # 記錄分割區、邏輯捲軸等資訊
        if device_type in ('part', 'lvm'):
            # 找出根本的物理磁碟
            root_disk = device_path
            path = device_path
            while path in disk_hierarchy:
                parent = disk_hierarchy[path]
                if parent in physical_disks:
                    root_disk = parent
                    break
                path = parent
            
            device_info = {
                'device': device_path,
                'type': device_type,
                'size': device_size,
                'size_mb': convert_to_mb(device_size),
                'physical_disk': root_disk,  # 此設備所屬的實體磁碟
                'mount_point': mount_point
            }
            
            logical_volumes[device_path] = device_info
            
            # 將此分割區/邏輯捲軸添加到實體磁碟的記錄中
            if root_disk in physical_disks:
                physical_disks[root_disk]['partitions'].append(device_path)
                if mount_point:  # 如果有掛載點，也記錄下來
                    physical_disks[root_disk]['mount_points'].append(mount_point)
    
    # 使用df獲取使用率信息，使用MB作為標準單位
    df_cmd = "df -h -B M"  # 使用MB作為單位以確保一致性
    df_output = ssh.execute_command(df_cmd, "utf-8")
    
    if not df_output:
        return {'physical_disks': physical_disks, 'logical_volumes': logical_volumes, 'usage_data': {}}
    
    # 解析df輸出，獲取使用量資訊
    usage_data = {}
    lines = df_output.strip().split('\n')
    
    # 跳過標題行
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 6:
            filesystem = parts[0]
            size = parts[1]
            used = parts[2]
            available = parts[3]
            usage_percent = parts[4].rstrip('%')
            mount_point = ' '.join(parts[5:])  # 支援有空格的掛載點
            
            # 將大小轉換為MB以便於計算
            size_mb = convert_to_mb(size)
            used_mb = convert_to_mb(used)
            available_mb = convert_to_mb(available)
            
            # 記錄使用量資訊
            usage_data[mount_point] = {
                'filesystem': filesystem,
                'size': size,
                'size_mb': size_mb,
                'used': used,
                'used_mb': used_mb,
                'available': available,
                'available_mb': available_mb,
                'usage_percent': usage_percent
            }
            
            # 更新邏輯捲軸資訊
            for device_path, info in logical_volumes.items():
                if info['mount_point'] == mount_point:
                    logical_volumes[device_path].update({
                        'used': used,
                        'used_mb': used_mb,
                        'available': available,
                        'available_mb': available_mb,
                        'usage_percent': usage_percent
                    })
    
    # 找出與LVM相關的設備
    # 特別處理 mapper 設備名稱
    device_mapper_links = {}
    try:
        # 執行 ls -l 檢查 mapper 鏈接
        ls_cmd = "ls -l /dev/mapper/"
        ls_output = ssh.execute_command(ls_cmd, "utf-8")
        if ls_output:
            for line in ls_output.strip().split('\n'):
                if '->' in line:  # 如果是符號鏈接
                    parts = line.split()
                    if len(parts) >= 11:
                        link_name = '/dev/mapper/' + parts[8]
                        target = parts[10]
                        device_mapper_links[link_name] = target
    except Exception as e:
        print(f"無法獲取mapper信息: {e}")
    
    # 獲取VG信息
    vg_pv_mapping = {}
    try:
        vgs_cmd = "pvs --noheadings -o vg_name,pv_name"
        vgs_output = ssh.execute_command(vgs_cmd, "utf-8")
        if vgs_output:
            for line in vgs_output.strip().split('\n'):
                parts = line.strip().split()
                if len(parts) >= 2:
                    vg_name = parts[0]
                    pv_name = parts[1]
                    if vg_name not in vg_pv_mapping:
                        vg_pv_mapping[vg_name] = []
                    vg_pv_mapping[vg_name].append(pv_name)
    except Exception as e:
        print(f"無法獲取VG信息: {e}")
    
    # 計算每顆實體磁碟的總使用量
    for disk_path, disk in physical_disks.items():
        total_used_mb = 0
        total_size_mb = 0
        total_available_mb = 0
        mount_usage = []
        
        # 首先檢查直接掛載在此實體磁碟上的分割區
        for partition in disk['partitions']:
            if partition in logical_volumes:
                part_info = logical_volumes[partition]
                
                # 如果此分割區有掛載點
                if part_info.get('mount_point') and part_info['mount_point'] in usage_data:
                    usage = usage_data[part_info['mount_point']]
                    mount_usage.append({
                        'mount_point': part_info['mount_point'],
                        'size_mb': usage['size_mb'],
                        'used_mb': usage['used_mb'],
                        'percent': usage['usage_percent']
                    })
                    total_size_mb += usage['size_mb']
                    total_used_mb += usage['used_mb']
                    total_available_mb += usage['available_mb']
        
        # 收集LVM信息 - 尋找與此實體磁碟相關的所有邏輯卷
        # 1. 找出此磁碟上哪些分割區是LVM物理捲
        related_pvs = []
        for partition in disk['partitions']:
            for vg_name, pv_list in vg_pv_mapping.items():
                if any(pv.startswith(partition) for pv in pv_list):
                    # 找到相關VG
                    # 現在檢查所有屬於此VG的LV
                    for fs_name, usage_info in usage_data.items():
                        fs_device = usage_info['filesystem']
                        
                        # 檢查此文件系統設備是否與VG相關
                        if f"/dev/mapper/{vg_name}-" in fs_device or vg_name in fs_device:
                            mount_usage.append({
                                'mount_point': fs_name,
                                'size_mb': usage_info['size_mb'],
                                'used_mb': usage_info['used_mb'],
                                'percent': usage_info['usage_percent']
                            })
                            total_size_mb += usage_info['size_mb']
                            total_used_mb += usage_info['used_mb']
                            total_available_mb += usage_info['available_mb']
        
        # 2. 檢查是否有任何mapper設備掛載在此磁碟上
        for fs_path, usage_info in usage_data.items():
            fs_device = usage_info['filesystem']
            # 檢查是否為mapper設備
            if fs_device.startswith('/dev/mapper/'):
                for partition in disk['partitions']:
                    # 如果此mapper設備與此分割區相關
                    # 這是一個簡化的檢查，實際上可能需要更複雜的邏輯
                    partition_base = partition.replace('/dev/', '')
                    if partition_base in fs_device or partition in device_mapper_links.get(fs_device, ''):
                        mount_usage.append({
                            'mount_point': fs_path,
                            'size_mb': usage_info['size_mb'],
                            'used_mb': usage_info['used_mb'],
                            'percent': usage_info['usage_percent']
                        })
                        total_size_mb += usage_info['size_mb']
                        total_used_mb += usage_info['used_mb']
                        total_available_mb += usage_info['available_mb']
        
        # 如果找到了掛載點
        if total_size_mb > 0:
            usage_percent = round((total_used_mb / total_size_mb) * 100, 1) if total_size_mb > 0 else 0
            disk['total_used_mb'] = total_used_mb
            disk['total_size_mb'] = total_size_mb
            disk['total_available_mb'] = total_available_mb
            disk['total_usage_percent'] = usage_percent
            disk['mount_usage'] = mount_usage
        else:
            disk['total_usage_percent'] = None
    
    # 整合資料
    disk_usage_info = {
        'physical_disks': physical_disks,
        'logical_volumes': logical_volumes,
        'usage_data': usage_data
    }
    
    return disk_usage_info

def format_size(size_mb):
    return f"{round(size_mb/1024, 1)}"

def get_windows_disk_usage(ssh):
    logicaldisk_cmd = 'powershell -Command "Get-CimInstance -ClassName Win32_logicalDisk -Filter "DriveType=3" | Select-Object -Property DeviceID, Size, FreeSpace | Format-Table -AutoSize"'
    logicaldisk_output = ssh.execute_command(logicaldisk_cmd, "cp950")
    if not logicaldisk_output:
        return {}
    
    disk_info = {}
    lines = logicaldisk_output.strip().splitlines()
    data_lines = [line for line in lines if ':' in line]

    for line in data_lines:
        parts = line.split()
        if len(parts) >= 3:
            device_id = parts[0]
            size_bytes = int(parts[1])
            free_bytes = int(parts[2])
            used_bytes = size_bytes - free_bytes

            size_gb = round(size_bytes / (1024 ** 3), 1)
            used_gb = round(used_bytes / (1024 ** 3), 1)

            disk_info[device_id] = {
                'size_gb': size_gb,
                'used_gb': used_gb
            }
    return disk_info

def insert_to_mssql(data):
    """
    raw data格式
    scanned_vms: [('S3_HAPROXY_allencloud', 5.7, 0, '2025-05-09'), ('CHC_PORD_Dashboard_ES', 5.7, 284.3, '2025-05-09'), ('CHC_SIT2_DBs', 5.7, 3.9, '2025-05-09'), ('CHC_SIT2_platform_DB', 5.7, 71.4, '2025-05-09')]

    目標MSSQL table格式
    CREATE TABLE T32_test.dbo.vm_usage (
        seq int IDENTITY(1,1) NOT NULL,
        vm_uuid varchar(255) COLLATE Chinese_Taiwan_Stroke_CI_AS NULL,
        c_storage float NULL,
        d_storage float NULL,
        use_date varchar(20) COLLATE Chinese_Taiwan_Stroke_CI_AS NULL
    );
    INSERT格式
    INSERT INTO T32_test.dbo.vm_usage (vm_uuid, c_storage, d_storage, use_date) VALUES('', 0, 0, '');
    """
    # 資料庫連接設定
    server = '10.210.175.48'  # 伺服器名稱或 IP 位址
    database = 'T32'        # 資料庫名稱
    username = 't32'   # 使用者名稱
    password = 'Chief26576688'   # 密碼

    # 建立連接字串
    conn_str = (
        f'DRIVER={{SQL Server}};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={username};'
        f'PWD={password}'
    )

    # 連接到資料庫
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        print("成功連接到 MSSQL 資料庫!")

        # 準備 INSERT 語句
        insert_query = """
        INSERT INTO T32.dbo.vm_usage 
        (vm_uuid, c_storage, d_storage, use_date) 
        VALUES (?, ?, ?, ?)
        """

        # 插入每一筆資料
        for vm_data in data:
            cursor.execute(insert_query, vm_data)
        
        # 提交交易
        conn.commit()
        print(f"成功插入 {len(data)} 筆資料!")

    except Exception as e:
        print(f"發生錯誤: {str(e)}")
        
    finally:
        # 關閉連接
        if 'conn' in locals() and conn:
            conn.close()
            print("資料庫連接已關閉")

def get_freebsd_disk_usage(ssh):
    df_cmd = "df -m /"
    output = ssh.execute_command(df_cmd, "utf-8")

    lines = output.strip().split("\n")
    data_line = lines[1]
    used_space = int(data_line.split()[2])
    used_space = round(used_space / 1024, 1)
    return used_space

if __name__ == "__main__":
    starttime = time.time()
    # excute_date = time.strftime('%Y-%m-%d')
    excute_date = "2025-06-30"

    targets = []
    scanned_vms = []
    scanned_failed_vms = []

    # 從JSON文件中讀取目標主機
    with open("chc_target.json") as json_file:
        json_targets = json.load(json_file)
        targets.extend(json_targets)

    ssh = SSHClient()

    # 在主循環中使用此函數
    for target in targets:
        c_storage_usage = 0
        d_storage_usage = 0
        try:
            # 嘗試SSH連接到目標主機
            ssh.connect(target["ip"], target["port"], target["user"], target["pwd"])
            
            # 輸出磁碟使用情況
            print(f"\n===== VM: {target['name']} ({target['ip']}) =====")
            
            # 獲取所有磁碟的使用情況
            if target["os"] == "linux":
                disk_info = get_linux_disk_usage(ssh)

                # 輸出物理磁碟資訊
                print("\n實體磁碟資訊:")
                for disk_path, disk in disk_info['physical_disks'].items():
                    print(f"磁碟路徑: {disk_path}")
                    print(f"大小: {disk['size']}")
                    
                    # 輸出磁碟總用量
                    # print(f"分割區/邏輯捲軸: {', '.join(disk['partitions'])}")
                    
                    if disk.get('total_usage_percent') is not None:
                        used = float(format_size(disk['total_used_mb']))
                        total = format_size(disk['total_size_mb'])
                        available = format_size(disk['total_available_mb'])
                        print(f"使用量總計: {used} GB")
                        """
                        print(f"使用率總計: {used}/{total} ({disk['total_usage_percent']}%)")
                        print(f"可用空間: {available}")

                        # 顯示各掛載點詳細資訊
                        if disk.get('mount_usage'):
                            print("掛載點詳細:")
                            for mount in disk['mount_usage']:
                                m_size = format_size(mount['size_mb'])
                                m_used = format_size(mount['used_mb'])
                                print(f"  - {mount['mount_point']}: {m_used}/{m_size} ({mount['percent']}%)")
                        """
                    else:
                        print("使用率總計: 無法計算 (沒有相關掛載點)")
                    
                    print("")

                    if c_storage_usage == 0:
                        c_storage_usage = used
                    else:
                        d_storage_usage = used

            elif target["os"] == "windows":
                disk_info = get_windows_disk_usage(ssh)

                # 輸出物理磁碟資訊
                print("\n實體磁碟資訊:")
                for disk_path, disk in disk_info.items():
                    print(f"磁碟路徑: {disk_path}")
                    print(f"大小: {disk['size_gb']} GB")
                    print(f"使用量總計: {disk['used_gb']} GB\n")

                    if c_storage_usage == 0:
                        c_storage_usage = disk['used_gb']
                    else:
                        d_storage_usage = disk['used_gb']

            elif target["os"] == "freebsd":
                # freebsd目前沒有設計撈取磁區結構
                disk_info = get_freebsd_disk_usage(ssh)

                print("\n實體磁碟資訊: N/A")
                print(f"使用量總計: {disk_info} GB\n")
                c_storage_usage = disk_info

            # 記錄掃描結果
            scanned_vms.append((target["name"], c_storage_usage, d_storage_usage, excute_date))
                
        except (paramiko.AuthenticationException, paramiko.SSHException, socket.timeout, Exception) as e:
            scanned_failed_vms.append((target["ip"], target["name"]))
            print(f"連線到 {target['ip']} 時發生錯誤: {e}")
            continue
        finally:
            ssh.close()

    print(f"scanned_vms: {scanned_vms}")

    endtime = time.time()
    deltatime = endtime - starttime
    print(f"\n掃描完成!")
    print(f"時間使用: {round(deltatime, 1)}秒")
    print(f"成功掃描: {len(scanned_vms)} 台")
    print(f"失敗掃描: {len(scanned_failed_vms)} 台")

    insert_to_mssql(scanned_vms)

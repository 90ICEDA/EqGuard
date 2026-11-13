import os
import re

def count_trojan_gates(folder_path, output_txt_path):
    """
    遍历文件夹中的.v文件，统计Trojan和Normal门的数量。
    """
    # Verilog 关键字，用于排除非门实例的行（如 module 定义、IO 声明等）
    verilog_keywords = {
        'module', 'input', 'output', 'wire', 'reg', 'assign', 
        'parameter', 'endmodule', 'primitive', 'always', 'edge'
    }

    # 正则表达式说明：
    # \b(\w+)\b : 第一个单词（门类型），捕获到 Group 1
    # \s+ : 至少一个空格
    # ([a-zA-Z0-9_\\/\[\]\.]+) : 第二个单词（实例名），支持转义符、括号等，捕获到 Group 2
    # \s*\( : 紧跟一个左括号，表示这是一个实例调用
    gate_pattern = re.compile(r'\b(\w+)\b\s+([a-zA-Z0-9_\\/\[\]\.]+)\s*\(')

    results = []
    
    # 检查输入路径
    if not os.path.isdir(folder_path):
        print(f"错误: 文件夹路径不存在 -> {folder_path}")
        return

    # 获取所有 .v 文件
    v_files = [f for f in os.listdir(folder_path) if f.endswith('.v')]
    
    if not v_files:
        print("提示: 文件夹中没有找到 .v 文件。")
        return

    print(f"开始处理 {len(v_files)} 个文件...")

    for file_name in v_files:
        file_path = os.path.join(folder_path, file_name)
        trojan_count = 0
        normal_count = 0

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # 1. 移除注释以防干扰统计
            content = re.sub(r'//.*', '', content)
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

            # 2. 匹配所有实例
            matches = gate_pattern.findall(content)

            for cell_type, inst_name in matches:
                # 排除 Verilog 声明关键字 (如 input, wire 等)
                if cell_type.lower() in verilog_keywords:
                    continue

                # 判断逻辑：实例名中包含 "trojan" 字样则视为木马门
                if 'trojan' in inst_name.lower():
                    trojan_count += 1
                else:
                    normal_count += 1

            results.append(f"文件: {file_name}\n  Normal 门数量: {normal_count}\n  Trojan 门数量: {trojan_count}\n" + "-"*30)
            print(f"已完成: {file_name} (Normal: {normal_count}, Trojan: {trojan_count})")

        except Exception as e:
            print(f"处理文件 {file_name} 时出错: {e}")

    # 3. 写入结果到 TXT
    try:
        with open(output_txt_path, 'w', encoding='utf-8') as out_f:
            out_f.write("硬件木马统计报告\n")
            out_f.write("="*40 + "\n")
            out_f.write("\n".join(results))
        print(f"\n[成功] 统计结果已记录在: {output_txt_path}")
    except Exception as e:
        print(f"写入文件时出错: {e}")

# ================= 使用示例 =================
if __name__ == "__main__":
    # 请在这里修改你的路径
    input_folder = r'nets' # 替换为你的.v文件夹路径
    output_log = 'log\cal.txt'                    # 结果保存的文件名

    count_trojan_gates(input_folder, output_log)
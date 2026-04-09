import json
import uuid


# 读取 JSON 文件
def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data


# 生成唯一的随机 ID
def generate_random_id():
    return str(uuid.uuid4())


# 替换 ID 为随机 ID
def replace_ids_with_random(data):
    id_mapping = {}
    for node in data['nodes']:
        old_id = node['id']
        new_id = generate_random_id()
        id_mapping[old_id] = new_id
        node['id'] = new_id

    for relation in data['relationships']:
        relation['from'] = id_mapping[relation['from']]
        relation['to'] = id_mapping[relation['to']]

    return data


# 保存 JSON 文件
def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


# 主函数
def main():
    input_file_path = "../../kg_output/test/0.json"
    output_file_path = input_file_path

    # 加载现有 JSON 数据
    data = load_json(input_file_path)

    # 替换 ID 为随机 ID
    updated_data = replace_ids_with_random(data)

    # 保存更新后的 JSON 数据
    save_json(updated_data, output_file_path)
    print(f"Updated JSON data saved to {output_file_path}")


# 运行主函数
if __name__ == "__main__":
    main()
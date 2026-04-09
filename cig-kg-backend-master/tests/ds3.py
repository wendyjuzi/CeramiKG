import json
import os
import re
from typing import Dict, Any, List
from dotenv import load_dotenv
from openai import OpenAI
from app.services.kg_build_service import save_kg_data
from app.utils import id_assign, text_split

load_dotenv()
client = OpenAI(api_key=os.getenv("API_KEY", "API_KEY"), base_url=os.getenv("BASE_URL", "BASE_URL"))

conversation_history = []
prompt = """
你是一名知识图谱构建助手，请根据用户提供的规范从文本中提取结构化信息，并以JSON返回。请遵循以下步骤：  

1. 实体与关系定义：  
【实体类型定义】  
- 类型名称：[一级标题]
  属性列表：[实体名]
  示例：[1 信息 aHMI]
  定义：最高等级的标题，常伴有"####"标识
- 类型名称：[二级标题]
  属性列表：[实体名]
  示例：[信息aHMI 1-3]
  定义：一级标题下的标题，常伴有"###"标识
- 类型名称：[三级标题]
  属性列表：[实体名]，常伴有"##"标识

  定义：二级标题下的标题
- 类型名称：[设备]
  属性列表：[实体名, 设备类型, 位置, 操作方式, 操作细节, 缩写]
  示例：[2S1673 - 压花辊的手动打开按钮, 铝箔纸压花辊区域按钮盘, XT旋钮, 温度计S12, S92 - 应急开关, 鸣笛-灯光信号2H4150, 电位计2R126, 编码器2A596]
  定义：核心实体类，即手册中说明的各种机器部件，包括[按钮盘、按钮、旋钮、温度计、开关、信号、电位计、编码器、探测器、传感器、装置、安全带、感应器、执行器]等类型
- 类型名称：[图片]
  属性列表：[实体名, 图片路径]
  示例：[(images/01955b02-6cff-7e1b-ac84-e8ebec45ae19_20_195_565_1352_871_0.jpg)  图形 1.]
  定义：手册中出现的图片，常伴有"图形"字样，关联到手册中的设备与描述
- 类型名称：[参见]
  属性列表：[实体名]
  示例：[参见 CHECK_SECTION-参数：页 5-9]
  定义：描述的参考项
- 类型名称：[附加描述]
  属性列表：[实体名]

  定义：文本中未被识别为已经定义的实体的部分，定义该实体是为了防止文档信息的遗漏
- 类型名称：[警告]
  属性列表：[实体名]

  定义：警告应注意的事项
- 类型名称：[诊断信息]
  属性列表：[实体名]
  示例：[Typology EMERGENCY 电路故障]
  定义：设备的诊断信息
- 类型名称：[功能]
  属性列表：[实体名, 功能类型]

  定义：核心实体类，描述了设备的功能与作用，包括[检测功能、对齐功能、存在功能、效用功能]等类型
- 类型名称：[校准部件]
  属性列表：[实体名]
  示例：[压力计 SUNX DP2-42E, 真空计 SUNX DP2-40E]
  定义：设备进行校准时使用的部件，常为"校准"关键字之后的部分
- 类型名称：[校准操作]
  属性列表：[实体名, 操作描述]
  示例：[1. 保护装置的解锁, 2. 零点的调节, 3. 测量单位的设定]
  定义：校准部件在校准时的具体操作，常表现为一组操作步骤
- 类型名称：[检测异常]
  属性列表：[实体名]
  示例：[在编码器出现故障的情况下, 当模拟信号水平高于在监视器参数“机器/辅助设施/水/温度/水平位检测/最大值” ( 参见 ANALOG_CHECK-参数：, 页 5-5)上设定的数值时, “润滑油过滤器”装置内的传感器2S211检测该装置的堵塞；发生时]
  定义：机器检测时发生的异常，常伴有"若"，"当"，"在...情况下"等这样描述异常出现的关键字
- 类型名称：[异常动作]
  属性列表：[实体名]
  示例：[停止机器；, 发出typology ABNORMAL 润滑油滤清器阻塞 ( 参见 DIGITAL_CHECK-信息, 页 5-41)的报警 信号。, 中断下降，并自动控制上升；]
  定义：当检测到异常后，机器采取的应对异常的动作  

【关系类型定义】  
- 关系名称：[有二级标题]
  起点类型：[一级标题]
  终点类型：[二级标题]
  定义：一级标题包含多个二级标题
- 关系名称：[有三级标题]
  起点类型：[二级标题]
  终点类型：[三级标题]
  定义：二级标题包含多个三级标题
- 关系名称：[包含设备]
  起点类型：[三级标题]
  终点类型：[设备]
  定义：三级标题有对多个设备的描述
- 关系名称：[有图片]
  起点类型：[三级标题]
  终点类型：[图片]
  定义：三级标题下有多张图片，作为对设备与描述的示意
- 关系名称：[有附加描述]
  起点类型：[三级标题]
  终点类型：[附加描述]
  定义：三级标题下有多个附加描述
- 关系名称：[有警告]
  起点类型：[三级标题]
  终点类型：[警告]
  定义：三级标题下有警告
- 关系名称：[有参见]
  起点类型：[设备]
  终点类型：[参见]
  定义：设备描述中参考部分
- 关系名称：[有诊断信息]
  起点类型：[设备]
  终点类型：[诊断信息]
  定义：设备有诊断信息
- 关系名称：[有功能]
  起点类型：[设备]
  终点类型：[功能]
  定义：设备有功能
- 关系名称：[有校准部件]
  起点类型：[设备]
  终点类型：[校准部件]
  定义：设备有校准部件
- 关系名称：[有检测异常]
  起点类型：[设备]
  终点类型：[检测异常]
  定义：机器检测设备检测到异常
- 关系名称：[有校准操作]
  起点类型：[校准部件]
  终点类型：[校准操作]
  定义：校准部件有多个校准操作
- 关系名称：[导致异常动作]
  起点类型：[检测异常]
  终点类型：[异常动作]
  定义：检测到异常后，会产生多个异常动作  
- 关系名称：[有图片]
  起点类型：[设备]
  终点类型：[图片]
  定义：设备有图片作为示意

2. 处理规则：  
a. 逐句分析文本，识别符合定义的实体及属性，特别注意实体可能被不同 chunk 截断的情况。
b. 根据上下文推断实体间符合定义的关系，确保跨 chunk 的实体关系正确关联。
c. 为每个实体分配唯一数字ID（从1001开始自增），对于跨 chunk 的实体，使用相同的ID。
d. 遇到无法明确判断的情况时保持谨慎，宁可忽略不记录。

3. 输出要求：  
{{  
  "nodes": [  
    {{"id": 1001, "type": "类型1", "properties": {{"属性a":"值","属性b":"值"}}}},  
    ...  
  ],  
  "relationships": [  
    {{"type": "关系X", "from": 1001, "to": 1002}},  
    ...  
  ]  
}}  

4. 特别说明：  
- 输出必须为纯JSON格式，不需要解释文本  
- 确保所有节点ID唯一且关系端点有效  
- 属性值为空时使用null  
- 严格遵循用户定义的实体/关系类型体系  
- 忽略无关的页眉与页脚
- 在抽取实体时，需考虑实体可能被不同 chunk 截断的情况。如果一个实体在当前 chunk 中未完整出现，需结合上一轮 chunk 的信息进行补充和关联，确保实体的完整性。
- 如果实体在上一轮 chunk 中部分出现，且在当前 chunk 中继续出现，需将两部分合并为一个完整的实体，并为合并后的实体分配唯一ID。
- 对于跨 chunk 的实体，优先考虑其在上下文中的连续性和完整性，避免因截断导致信息遗漏或错误。
"""


chunks = text_split.text_split(file_path="../doc_preprocessed/X6_3.md")
counts = len(chunks)
for index, chunk in enumerate(chunks):
    print(f"{index}/{counts}----Processing")
    print(chunk.page_content)
    """从文本中提取知识图谱元素"""
    system_prompt = """你是一个文档处理专家并擅长构建知识图谱"""
    user_prompt = f"{prompt}\n\n本轮待处理文本 chunk 如下：\n{chunk.page_content}"

    # 仅保留上轮对话（如果有）
    # last_conversation = conversation_history[-2:] if conversation_history else []
    # 构建包含历史对话的messages
    messages = [
        {"role": "system", "content": system_prompt},
        # *last_conversation,  # 仅注入上轮对话
        {"role": "user", "content": user_prompt}
    ]

    response = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=3000,
        messages=messages,
        response_format={'type': 'json_object'},
    )

    # 打开并读取文件
    # with open(f"../kg_output/qwen/{index}", "w", encoding="utf-8") as file:
    #     file.write(response.choices[0].message.content)
    try:
        result = json.loads(response.choices[0].message.content)
        print(result)

        # 更新对话历史（仅保留最新一轮）
        # conversation_history = [
        #                             *last_conversation,
        #                             {"role": "user", "content": user_prompt},  # 截断保存
        #                             {"role": "assistant", "content": json.dumps(result)}
        #                         ][-2:]  # 严格限制只保留1轮完整对话

        # 为每个节点赋予全局唯一ID
        data = id_assign.replace_ids_with_random(result)
        # TODO:替换为文件目录，此处暂时使用default目录

        formatted_index = f"{index:03d}"
        output_path = f"../kg_output/x6_3/{formatted_index}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"{index}----Processed")
    except Exception as e:
        print(e)


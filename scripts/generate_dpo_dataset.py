#!/usr/bin/env python3
"""
生成DPO格式数据集（增量保存版本）
- chosen: 现有emention中的俏皮温柔风格回答
- rejected: 用大模型生成的正式官方风格回答
"""

import json
import os
import sys
from tqdm import tqdm
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# 配置
MODEL_PATH = "/root/autodl-tmp/llamafactory/saves/Qwen2.5-3B-Instruct/lora/train_2026-03-12-10-32-47"
INPUT_FILE = "/root/autodl-tmp/llamafactory/data/emention/train.jsonl"
OUTPUT_FILE = "/root/autodl-tmp/llamafactory/data/emention_dpo/train.jsonl"
MAX_SAMPLES = 100  # 减少样本数加快演示
MAX_NEW_TOKENS = 128  # 减少生成token数提速

FORMAL_SYSTEM_PROMPT = """你是一个专业的AI助手。请用正式、官方、专业的语言风格回答用户问题。
要求：
1. 使用书面语，避免口语化表达
2. 语气客观中立，不带个人情感
3. 回答简洁有条理，不超过50字
4. 避免使用表情符号、网络用语、感叹词"""

def load_model():
    """加载本地模型"""
    print(f"Loading model from {MODEL_PATH}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        device_map="auto",
        trust_remote_code=True
    )
    model.eval()
    return model, tokenizer

def generate_formal_response(model, tokenizer, user_message: str) -> str:
    """用模型生成正式风格的回答"""
    messages = [
        {"role": "system", "content": FORMAL_SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]
    
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=0.7,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )
    
    response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    return response.strip()

def convert_to_dpo_format(messages: list) -> dict:
    """将messages格式转换为DPO格式"""
    user_msg = ""
    assistant_msg = ""
    
    for msg in messages:
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
        elif msg.get("role") == "assistant":
            assistant_msg = msg.get("content", "")
    
    return {
        "conversations": [
            {"from": "human", "value": user_msg}
        ],
        "chosen": {
            "from": "gpt",
            "value": assistant_msg
        }
    }

def main():
    # 创建输出目录
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    # 读取原始数据
    print(f"Reading {INPUT_FILE}...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()[:MAX_SAMPLES]
    
    print(f"Processing {len(lines)} samples...")
    
    # 检查是否已有部分数据
    processed_count = 0
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            processed_count = sum(1 for _ in f)
        print(f"Found {processed_count} already processed samples, continuing...")
    
    # 加载模型
    model, tokenizer = load_model()
    
    # 处理每条数据
    dpo_data = []
    start_idx = processed_count
    
    for i, line in enumerate(tqdm(lines[start_idx:], desc="Generating DPO data")):
        try:
            data = json.loads(line)
            messages = data.get("messages", [])
            
            # 转换为DPO格式（chosen部分）
            dpo_item = convert_to_dpo_format(messages)
            
            # 提取用户问题
            user_msg = ""
            for msg in messages:
                if msg.get("role") == "user":
                    user_msg = msg.get("content", "")
                    break
            
            # 生成正式风格回答
            formal_response = generate_formal_response(model, tokenizer, user_msg)
            
            dpo_item["rejected"] = {
                "from": "gpt",
                "value": formal_response
            }
            
            dpo_data.append(dpo_item)
            
            # 每10条保存一次
            if len(dpo_data) >= 10:
                with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                    for item in dpo_data:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                print(f"\nSaved {len(dpo_data)} samples, total: {processed_count + len(dpo_data)}")
                dpo_data = []
            
        except Exception as e:
            print(f"Error processing line {i}: {e}")
            continue
    
    # 保存剩余数据
    if dpo_data:
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            for item in dpo_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    print(f"\nDone! Generated DPO samples.")

if __name__ == "__main__":
    main()

import json
import os
import openai
from tqdm import tqdm
import time

# 默认配置，基于 ceshi.py
DEFAULT_API_KEY = "sk-gX6gm6RQqR8NIDBgRMWyDzjOPhOQXI8PQb8DzB2v1SjEIfOF"
DEFAULT_BASE_URL = "https://automl.aiserverai.online/v1"
DEFAULT_MODEL = "gpt-4.1"

class LLMClient:
    def __init__(self, api_key: str = DEFAULT_API_KEY, base_url: str = DEFAULT_BASE_URL, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    def get_response(self, prompt: str) -> str:
        """发送单个提示词给大模型并获取回复。循环直到获取非空回复。"""
        while True:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                # 安全地获取内容，避免 'NoneType' object has no attribute 'strip' 错误
                content = response.choices[0].message.content
                if content and content.strip():
                    return content.strip()
                print("Warning: Received empty response from API. Retrying...")
            except Exception as e:
                print(f"Error calling API: {e}. Retrying...")

            # 简单的退避策略，避免过于频繁请求
            time.sleep(1)

    def process_prompts_file(self, input_file: str, output_file: str, progress_callback=None, stop_event=None):
        """
        处理包含提示词的 JSON 文件，并将回复保存到新文件。
        支持进度回调和停止事件。
        progress_callback: function(current, total)
        stop_event: threading.Event
        """
        if not os.path.exists(input_file):
            print(f"Error: Input file {input_file} not found.")
            return

        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # data 应该是 [{"original": "...", "jailbreak_prompt": "..."}, ...]
            results = []
            total = len(data)
            print(f"Sending {total} prompts to LLM ({self.model})...")

            # 如果已经存在部分结果，可以考虑断点续传（此处暂不实现复杂逻辑，仅覆盖）

            processed_count = 0
            for item in tqdm(data, desc="Processing LLM Requests"):
                if stop_event and stop_event.is_set():
                    print("Process stopped by user.")
                    break

                prompt = item.get("jailbreak_prompt", "")
                if not prompt:
                    processed_count += 1
                    if progress_callback:
                        progress_callback(processed_count, total)
                    continue

                response = self.get_response(prompt)

                # 保存原始信息、提示词和模型回复
                result_item = {
                    "original": item.get("original", ""),
                    "jailbreak_prompt": prompt,
                    "llm_response": response
                }
                results.append(result_item)

                processed_count += 1
                if progress_callback:
                    progress_callback(processed_count, total)

                # 简单的速率限制，避免过快
                # time.sleep(0.5)

            # 确保目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4, ensure_ascii=False)

            if stop_event and stop_event.is_set():
                print(f"Saved partial LLM responses to {output_file}")
            else:
                print(f"Saved LLM responses to {output_file}")

        except Exception as e:
            print(f"Error processing prompts file: {e}")

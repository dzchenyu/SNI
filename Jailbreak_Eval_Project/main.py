import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import pandas as pd
import json

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.jailbreak_generator import JailbreakGenerator
from src.api_client import LLMClient, DEFAULT_API_KEY, DEFAULT_BASE_URL, DEFAULT_MODEL
from src.evaluator import Evaluator

class JailbreakApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LLM 越狱实验平台")
        self.root.geometry("900x700")

        # Initialize Default Paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.base_dir, 'data')
        self.exp_data_dir = os.path.join(self.base_dir, 'exp_data')
        self.results_dir = os.path.join(self.base_dir, 'results')

        self.behaviors_file = os.path.join(self.data_dir, 'behaviors.json')
        self.moderation_file = os.path.join(self.data_dir, 'moderation.json')

        # Ensure directories exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)

        # Initialize Logic Components
        self.generator = JailbreakGenerator(moderation_path=self.moderation_file)
        self.client = None # Will init on run with current settings
        self.evaluator = Evaluator()

        self.setup_ui()

    def setup_ui(self):
        # Create Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.tab_run = ttk.Frame(self.notebook)
        self.tab_config = ttk.Frame(self.notebook)
        self.tab_utils = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_run, text="运行实验")
        self.notebook.add(self.tab_config, text="配置")
        self.notebook.add(self.tab_utils, text="工具")

        self.setup_config_tab()
        self.setup_run_tab()
        self.setup_utils_tab()

    def setup_config_tab(self):
        frame = ttk.LabelFrame(self.tab_config, text="设置", padding=10)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # API Settings
        api_frame = ttk.Frame(frame)
        api_frame.pack(fill='x', pady=5)

        ttk.Label(api_frame, text="[攻击模型配置] (用于生成攻击回复)").grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 5))

        ttk.Label(api_frame, text="模型名称:").grid(row=1, column=0, sticky='w', pady=5)
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        ttk.Entry(api_frame, textvariable=self.model_var, width=30).grid(row=1, column=1, sticky='w')

        ttk.Label(api_frame, text="API 基础 URL:").grid(row=2, column=0, sticky='w', pady=5)
        self.base_url_var = tk.StringVar(value=DEFAULT_BASE_URL)
        ttk.Entry(api_frame, textvariable=self.base_url_var, width=50).grid(row=2, column=1, sticky='w')

        ttk.Label(api_frame, text="API 密钥:").grid(row=3, column=0, sticky='w', pady=5)
        self.api_key_var = tk.StringVar(value=DEFAULT_API_KEY)
        ttk.Entry(api_frame, textvariable=self.api_key_var, show="*", width=50).grid(row=3, column=1, sticky='w')

        # Evaluator API Settings (Judge)
        ttk.Separator(api_frame, orient='horizontal').grid(row=4, column=0, columnspan=2, sticky='ew', pady=10)
        ttk.Label(api_frame, text="[评估模型配置] (LLM Judge - gpt-4o-mini)").grid(row=5, column=0, columnspan=2, sticky='w', pady=(0, 5))

        ttk.Label(api_frame, text="评估 API URL:").grid(row=6, column=0, sticky='w', pady=5)
        self.judge_base_url_var = tk.StringVar(value=DEFAULT_BASE_URL)
        ttk.Entry(api_frame, textvariable=self.judge_base_url_var, width=50).grid(row=6, column=1, sticky='w')

        ttk.Label(api_frame, text="评估 API 密钥:").grid(row=7, column=0, sticky='w', pady=5)
        self.judge_api_key_var = tk.StringVar(value=DEFAULT_API_KEY)
        ttk.Entry(api_frame, textvariable=self.judge_api_key_var, show="*", width=50).grid(row=7, column=1, sticky='w')

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)

        # Generator Settings
        gen_frame = ttk.Frame(frame)
        gen_frame.pack(fill='x', pady=5)

        ttk.Label(gen_frame, text="策略:").grid(row=0, column=0, sticky='w', pady=5)
        self.strategy_var = tk.StringVar(value="Strategy C")
        strategy_cb = ttk.Combobox(gen_frame, textvariable=self.strategy_var, values=list(self.generator.strategies.keys()))
        strategy_cb.grid(row=0, column=1, sticky='w')
        strategy_cb.bind("<<ComboboxSelected>>", self.on_strategy_change)

        ttk.Label(gen_frame, text="混淆符号:").grid(row=1, column=0, sticky='w', pady=5)
        self.obfuscation_char_var = tk.StringVar(value="*")
        self.obfuscation_char_entry = ttk.Entry(gen_frame, textvariable=self.obfuscation_char_var, width=5)
        self.obfuscation_char_entry.grid(row=1, column=1, sticky='w')

        # Safe Words Count (Strategy B)
        ttk.Label(gen_frame, text="良性词数量 (Strategy B):").grid(row=2, column=0, sticky='w', pady=5)
        self.safe_words_count_var = tk.IntVar(value=1)
        self.safe_words_count_spin = ttk.Spinbox(gen_frame, from_=1, to=10, textvariable=self.safe_words_count_var, width=5)
        self.safe_words_count_spin.grid(row=2, column=1, sticky='w', pady=5)

        self.enable_obfuscation_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(gen_frame, text="启用混淆", variable=self.enable_obfuscation_var).grid(row=3, column=1, sticky='w', pady=5)

        # Template Editor
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(frame, text="提示词模板编辑 (使用 {payload}, {char}, {char_name} 作为占位符):").pack(anchor='w', pady=5)

        self.template_text = scrolledtext.ScrolledText(frame, height=10)
        self.template_text.pack(fill='both', expand=True, pady=5)

        # Load initial template
        self.load_current_template()

        ttk.Button(frame, text="保存配置与模板", command=self.save_config_and_template).pack(pady=10)


    def setup_run_tab(self):
        # Input Section
        input_frame = ttk.LabelFrame(self.tab_run, text="输入选择", padding=10)
        input_frame.pack(fill='x', padx=10, pady=5)

        self.mode_var = tk.StringVar(value="input")
        ttk.Radiobutton(input_frame, text="单条输入", variable=self.mode_var, value="input", command=self.toggle_input_mode).grid(row=0, column=0, sticky='w')
        ttk.Radiobutton(input_frame, text="文件输入", variable=self.mode_var, value="file", command=self.toggle_input_mode).grid(row=0, column=1, sticky='w')

        # Single Input
        self.single_input_frame = ttk.Frame(input_frame)
        self.single_input_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)
        ttk.Label(self.single_input_frame, text="提示词文本:").pack(anchor='w')
        self.text_input = tk.Text(self.single_input_frame, height=3, width=80)
        self.text_input.pack(fill='x')

        # File Input
        self.file_input_frame = ttk.Frame(input_frame)
        self.file_input_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)
        ttk.Label(self.file_input_frame, text="输入文件:").pack(side='left')
        self.file_path_var = tk.StringVar(value=self.behaviors_file)
        ttk.Entry(self.file_input_frame, textvariable=self.file_path_var, width=50).pack(side='left', padx=5)
        ttk.Button(self.file_input_frame, text="浏览", command=self.browse_file).pack(side='left')
        self.file_input_frame.grid_remove() # Hide initially

        # Actions
        action_frame = ttk.Frame(self.tab_run, padding=10)
        action_frame.pack(fill='x', padx=10)
        self.run_button = ttk.Button(action_frame, text="开始运行实验", command=self.run_experiment_thread)
        self.run_button.pack(side='left', padx=5)

        self.stop_button = ttk.Button(action_frame, text="终止实验", command=self.stop_experiment, state='disabled')
        self.stop_button.pack(side='left', padx=5)

        # Progress Bar
        progress_frame = ttk.Frame(self.tab_run, padding=10)
        progress_frame.pack(fill='x', padx=10)

        ttk.Label(progress_frame, text="进度:").pack(side='left')
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side='left', fill='x', expand=True, padx=5)
        self.progress_label = ttk.Label(progress_frame, text="0%")
        self.progress_label.pack(side='left')

        # Output Console
        output_frame = ttk.LabelFrame(self.tab_run, text="输出 / 日志", padding=10)
        output_frame.pack(fill='both', expand=True, padx=10, pady=5)
        self.console = scrolledtext.ScrolledText(output_frame, state='disabled', height=15)
        self.console.pack(fill='both', expand=True)

    def setup_utils_tab(self):
        frame = ttk.LabelFrame(self.tab_utils, text="数据工具", padding=10)
        frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(frame, text="从 CSV 提取 'goal' 到 JSON:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Button(frame, text="转换 harmful_behaviors.csv", command=self.convert_csv_to_json).grid(row=0, column=1, padx=10)

    def toggle_input_mode(self):
        if self.mode_var.get() == "input":
            self.file_input_frame.grid_remove()
            self.single_input_frame.grid()
        else:
            self.single_input_frame.grid_remove()
            self.file_input_frame.grid()

    def browse_file(self):
        filename = filedialog.askopenfilename(initialdir=self.data_dir, title="选择输入文件", filetypes=(("JSON files", "*.json"), ("All files", "*.*")))
        if filename:
            self.file_path_var.set(filename)

    def log(self, message):
        self.console.config(state='normal')
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state='disabled')

    def load_current_template(self):
        strategy = self.strategy_var.get()
        template = self.generator.strategies.get(strategy, "")
        self.template_text.delete("1.0", tk.END)
        self.template_text.insert("1.0", template)

    def on_strategy_change(self, event):
        self.load_current_template()
        if self.strategy_var.get() == "Strategy B":
            self.obfuscation_char_entry.config(state='disabled')
            self.safe_words_count_spin.config(state='normal')
        else:
            self.obfuscation_char_entry.config(state='normal')
            self.safe_words_count_spin.config(state='disabled')

    def save_config_and_template(self):
        # Update config
        try:
            current_strategy = self.strategy_var.get()
            custom_template = self.template_text.get("1.0", tk.END).strip()

            # Ensure safe_words_count is valid
            try:
                safe_words_count = int(self.safe_words_count_var.get())
            except ValueError:
                safe_words_count = 1

            self.generator.update_config(
                strategy=current_strategy,
                obfuscation_char=self.obfuscation_char_var.get(),
                obfuscation_enabled=self.enable_obfuscation_var.get(),
                custom_template=custom_template,
                safe_words_count=safe_words_count
            )

             # Re-initialize client
            self.client = LLMClient(api_key=self.api_key_var.get(), base_url=self.base_url_var.get(), model=self.model_var.get())

            self.log(f"配置已更新。策略: {current_strategy}")
            messagebox.showinfo("成功", "配置与模板已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")

    def update_generator_config(self):
        # Allow run to grab latest even if not explicitly saved via button,
        # but prefer the saved state. In this flow, we might want to just call save_config logic
        # or assume "Run" uses what is currently in the generator object.
        # For simplicity, we'll sync from UI just in case.

        # But wait, we added a dedicated "Save" button for the template.
        # Let's ensure run_experiment calls update_config too or assumes the user clicked save.
        # Safest is to sync from vars, except template text which might be heavy to read every time?
        # Let's read it.

        current_strategy = self.strategy_var.get()
        custom_template = self.template_text.get("1.0", tk.END).strip()

        self.generator.update_config(
            strategy=current_strategy,
            obfuscation_char=self.obfuscation_char_var.get(),
            obfuscation_enabled=self.enable_obfuscation_var.get(),
            custom_template=custom_template
        )
        # Re-initialize client if key/url changed
        self.client = LLMClient(api_key=self.api_key_var.get(), base_url=self.base_url_var.get(), model=self.model_var.get())

    def convert_csv_to_json(self):
        csv_path = os.path.join(self.exp_data_dir, 'harmful_behaviors.csv')
        json_path = os.path.join(self.data_dir, 'behaviors.json')

        if not os.path.exists(csv_path):
            messagebox.showerror("错误", f"未找到 CSV 文件: {csv_path}")
            return

        try:
            df = pd.read_csv(csv_path)
            if 'goal' in df.columns:
                goals = df['goal'].dropna().tolist()
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(goals, f, indent=4, ensure_ascii=False)
                self.log(f"成功将 {len(goals)} 个目标从 CSV 转换到 {json_path}")
                messagebox.showinfo("成功", f"转换了 {len(goals)} 条数据到 {json_path}")
            else:
                messagebox.showerror("错误", "CSV 中未找到 'goal' 列。")
        except Exception as e:
            self.log(f"转换 CSV 时出错: {e}")
            messagebox.showerror("错误", str(e))

    def stop_experiment(self):
        if hasattr(self, 'is_running') and self.is_running:
            self.stop_event.set()
            self.log("正在终止实验...")
            self.stop_button.config(state='disabled')

    def run_experiment_thread(self):
        self.stop_event = threading.Event()
        self.is_running = True
        self.run_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.update_progress(0, 100, "")
        threading.Thread(target=self.run_experiment, daemon=True).start()

    def update_progress(self, current, total, prefix=""):
        if total > 0:
            percentage = (current / total) * 100
        else:
            percentage = 0
        self.root.after(0, lambda: self._update_progress_ui(percentage, f"{prefix} {int(percentage)}%"))

    def _update_progress_ui(self, value, text):
        self.progress_var.set(value)
        self.progress_label.config(text=text)

    def run_experiment(self):
        self.update_generator_config()
        # 更新 Evaluator 配置 (使用当前 API Key/URL，指定模型为 gpt-4o-mini)
        self.evaluator = Evaluator(
            api_key=self.judge_api_key_var.get(),
            base_url=self.judge_base_url_var.get(),
            model="gpt-4o-mini"
        )

        self.log("=== 开始实验 ===")

        mode = self.mode_var.get()

        if mode == "input":
            text = self.text_input.get("1.0", tk.END).strip()
            if not text:
                self.log("错误: 请输入文本。")
                return

            self.log(f"输入: {text}")

            # Step 1: Generate
            self.log("正在生成提示词...")
            try:
                obfuscated = self.generator.process_sentence_with_detoxify(text)
                jailbreak_prompt = self.generator.generate_prompt(obfuscated)
                self.log(f"生成的提示词 (已截断):\n{jailbreak_prompt[:200]}...")
            except Exception as e:
                self.log(f"生成提示词出错: {e}")
                return

            # Step 2: Attack
            self.log("正在发送给大模型...")
            response = self.client.get_response(jailbreak_prompt)
            self.log(f"模型回复:\n{response}")

            # Step 3: Evaluate
            is_success, rating = self.evaluator.evaluate_response(response, prompt=text)
            result_str = f"越狱成功 (By Judge, Score: {rating})" if is_success else f"越狱失败 (Score: {rating})"
            self.log(f"评估结果: {result_str}")

            if is_success:
                self.log(f"判定通过: 无拒绝词且 LLM 裁判打分 {rating} >= 4")
            else:
                self.log(f"判定未通过: 包含拒绝词或 LLM 裁判打分 {rating} < 4")


        elif mode == "file":
            input_file = self.file_path_var.get()
            if not os.path.exists(input_file):
                self.log(f"错误: 未找到文件 {input_file}。")
                self.reset_ui_state()
                return

            generated_prompts_file = os.path.join(self.results_dir, 'jailbreak_prompts.json')
            llm_responses_file = os.path.join(self.results_dir, 'llm_responses.json')
            evaluation_results_file = os.path.join(self.results_dir, 'evaluation_results.json')

            # Step 1: Generate
            if self.stop_event.is_set():
                self.reset_ui_state()
                return
            self.log(f"正在处理文件: {input_file}...")
            self.generator.process_file(input_file, generated_prompts_file)
            self.log(f"提示词已保存至 {generated_prompts_file}")

            # Step 2: Attack
            if self.stop_event.is_set():
                self.reset_ui_state()
                return
            self.log("正在将提示词发送给大模型 (这可能需要一些时间)...")
            self.update_progress(0, 100, "攻击进度")

            def attack_progress(current, total):
                self.update_progress(current, total, "攻击进度")

            self.client.process_prompts_file(generated_prompts_file, llm_responses_file, progress_callback=attack_progress, stop_event=self.stop_event)

            if self.stop_event.is_set():
                self.log("攻击过程已终止。")
                self.reset_ui_state()
                return

            self.log(f"回复已保存至 {llm_responses_file}")

            # Step 3: Evaluate
            if self.stop_event.is_set():
                self.reset_ui_state()
                return
            self.log("正在评估结果...")
            self.update_progress(0, 100, "评估进度")

            def eval_progress(current, total):
                self.update_progress(current, total, "评估进度")

            asr = self.evaluator.evaluate_file(llm_responses_file, evaluation_results_file, progress_callback=eval_progress, stop_event=self.stop_event)

            if self.stop_event.is_set():
                self.log("评估过程已终止。")
                self.reset_ui_state()
                return

            self.log(f"=== 实验完成 ===")
            # 使用 .get() 获取 StringVar 的实际值
            self.log(f"模型: {self.model_var.get()} - 攻击成功率 (ASR): {asr:.2%}")

        self.reset_ui_state()

    def reset_ui_state(self):
        self.is_running = False
        self.root.after(0, lambda: self.run_button.config(state='normal'))
        self.root.after(0, lambda: self.stop_button.config(state='disabled'))
        self.update_progress(0, 100, "就绪")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = JailbreakApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Error starting GUI: {e}")

import ollama

# 推荐使用 chat 方法（更接近对话场景）
response = ollama.chat(
    model="deepseek-r1:8b",
    messages=[{"role": "user", "content": "你好介绍一下自己"}],


    stream=True
)

# 流式输出
for chunk in response:
    print(chunk["message"]["content"], end="", flush=True)
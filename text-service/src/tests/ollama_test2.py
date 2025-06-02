import requests
import json


def test_ollama_model(prompt, model_name="deepseek-coder:1.3b", ollama_host="http://localhost:11434"):
    """
    测试Ollama运行的模型

    参数:
        prompt: 要发送给模型的提示文本
        model_name: 模型名称(默认为deepseek-coder:1.3b)
        model_name: 模型名称(默认为deepseek-r1:8b)
        ollama_host: Ollama服务地址(默认为http://localhost:11434)

    返回:
        模型的响应内容
    """
    url = f"{ollama_host}/api/generate"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model_name,
        "prompt": prompt,
        "stream": False  # 设置为False以获取完整响应
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        return response.json().get("response", "No response from model")
    except requests.exceptions.RequestException as e:
        return f"Error communicating with Ollama: {str(e)}"


if __name__ == "__main__":
    # 测试代码生成能力
    code_prompt = "介绍下你自己"
    print(f"测试提示: {code_prompt}")
    code_response = test_ollama_model(code_prompt)
    print("\n模型响应:")
    print(code_response)


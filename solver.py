import requests
import json
import matplotlib.pyplot as plt
import numpy as np
import io
from math import sin, cos, tan, log, sqrt, exp, pi, e
from config import OPENROUTER_API_KE

def solve_math(text):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Ты — репетитор по математике, физике и химии. Решай пошагово. НЕ используй LaTeX."},
            {"role": "user", "content": text}
        ],
        "temperature": 0.1
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        if "error" in result:
            return f"❌ Ошибка OpenRouter: {result['error']['message']}"
        if "choices" in result:
            return result["choices"][0]["message"]["content"]
        return "❌ Неожиданный ответ"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def plot_function(expression):
    try:
        print(f"📊 Строю график: {expression}")
        x = np.linspace(-10, 10, 500)
        expr = expression.replace('^', '**')
        # Разрешаем использование математических функций
        allowed_names = {
            'sin': sin, 'cos': cos, 'tan': tan,
            'log': log, 'sqrt': sqrt, 'exp': exp,
            'pi': pi, 'e': e
        }
        y = eval(expr, {"__builtins__": {}}, allowed_names)
        plt.figure(figsize=(8, 6))
        plt.plot(x, y, linewidth=2, color='blue')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.axhline(y=0, color='black', linewidth=0.5)
        plt.axvline(x=0, color='black', linewidth=0.5)
        plt.title(f'График функции y = {expression}', fontsize=14)
        plt.xlabel('x')
        plt.ylabel('y')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        print(f"❌ Ошибка графика: {e}")
        return None

def transcribe_voice(file_path):
    try:
        url = "https://openrouter.ai/api/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {"model": "whisper-1", "language": "ru"}
            response = requests.post(url, headers=headers, files=files, data=data)
            result = response.json()
            if "text" in result:
                return result["text"].strip()
            return None
    except Exception as e:
        return None

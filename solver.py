import requests
import json
import matplotlib.pyplot as plt
import numpy as np
import io
import os
from config import OPENROUTER_API_KEY

# ===== РЕШЕНИЕ ЗАДАЧ ЧЕРЕЗ GPT =====
def solve_math(text):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "system", "content": 
             "Ты — супер-репетитор по математике, физике и химии. "
             "Решай задачи пошагово и понятно. "
             "НЕ используй LaTeX. Пиши формулы текстом: x^2, H2O, F=ma."
            },
            {"role": "user", "content": text}
        ],
        "temperature": 0.1
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        if "error" in result:
            return f"❌ Ошибка OpenRouter: {result['error']['message']}"
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        else:
            return f"❌ Неожиданный ответ: {json.dumps(result, indent=2, ensure_ascii=False)}"
    except Exception as e:
        return f"❌ Ошибка при обращении к OpenRouter: {str(e)}"

# ===== ГРАФИКИ =====
def plot_function(expression, var='x'):
    try:
        x = np.linspace(-10, 10, 500)
        expr = expression.replace('^', '**')
        y = eval(expr)
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
        return None

import whisper
import os

# Загружаем лёгкую модель Whisper (tiny)
whisper_model = whisper.load_model("tiny")

import whisper
import os

whisper_model = whisper.load_model("tiny")

def transcribe_voice(file_path):
    try:
        result = whisper_model.transcribe(file_path, language='ru')
        text = result['text'].strip()
        return text
    except Exception as e:
        return None

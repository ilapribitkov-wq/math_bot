import requests
import json
import matplotlib.pyplot as plt
import numpy as np
import io
import os
import subprocess
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
             "Если задача по химии — уравнивай реакции. "
             "Если по физике — используй формулы. "
             "В конце каждого решения добавляй короткий совет: 'Запомни: ...' "
             "НЕ используй LaTeX. Пиши формулы текстом: x^2, H2O, F=ma, 2H2 + O2 = 2H2O."
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



# 04_coach_replies.py
import argparse, json, os, sys
from pathlib import Path

try:
    from openai import OpenAI
except Exception as e:
    raise SystemExit("Не найден пакет 'openai'. Установите: pip install openai") from e

IMPORTED_OPENAI_KEY = "***REMOVED***"

SYSTEM_INSTRUCTIONS = (
    "Ты — коуч для телефонных продаж. На входе — размеченный диалог между менеджером и клиентом. "
    "Твоя задача — дать конкретные подсказки менеджеру для улучшения продаж.\n\n"
    "ФОРМАТ ОТВЕТА: только JSON с категориями подсказок:\n"
    "{\n"
    "  \"сейчас\": [\"подсказка 1\", \"подсказка 2\"],\n"
    "  \"скоро\": [\"что сказать дальше\"],\n"
    "  \"позже\": [\"стратегические советы\"],\n"
    "  \"возражения\": [\"как отвечать на возражения\"]\n"
    "}\n\n"
    "Подсказки должны быть короткими (до 180 символов) и конкретными."
)

def make_client(timeout: float = 30.0):
    api_key = IMPORTED_OPENAI_KEY or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Не найден API-ключ OpenAI")
    return OpenAI(api_key=api_key, timeout=timeout)

def call_openai(model: str, instructions: str, user_input: str, timeout: float = 30.0) -> str:
    client = make_client(timeout=timeout)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_input}
        ],
        temperature=0.7,
        max_tokens=1000
    )
    return resp.choices[0].message.content.strip()

def generate_coach_suggestions(dialog_text: str, model: str, company: str, goal: str, tone: str, 
                             company_info: str = "", constraints: str = "") -> dict:
    prompt = f"""
ДИАЛОГ:
{dialog_text}

КОНТЕКСТ:
- Компания: {company}
- Цель: {goal}  
- Тон: {tone}
- Информация о компании: {company_info}
- Ограничения: {constraints}

Проанализируй диалог и дай подсказки менеджеру в формате JSON.
    """
    
    try:
        response = call_openai(model, SYSTEM_INSTRUCTIONS, prompt)
        return json.loads(response)
    except Exception as e:
        print(f"Ошибка генерации подсказок: {e}", file=sys.stderr)
        return {
            "сейчас": ["Активно слушайте клиента"],
            "скоро": ["Уточните потребности"],
            "позже": ["Предложите демо"],
            "возражения": ["Покажите понимание проблемы"]
        }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="путь к файлу диалога (.dialog.txt)")
    ap.add_argument("--model", default="gpt-4o-mini", help="модель OpenAI")
    ap.add_argument("--company", default="ВестКолл", help="имя компании")
    ap.add_argument("--goal", default="привлечь клиента", help="цель продаж")
    ap.add_argument("--tone", default="дружелюбный", help="тональность")
    ap.add_argument("--company-info", default="", help="информация о компании")
    ap.add_argument("--constraints", default="", help="ограничения")
    ap.add_argument("--also-txt", action="store_true", help="сохранить также .txt версию")
    args = ap.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        raise SystemExit(f"Файл не найден: {inp}")

    dialog_text = inp.read_text(encoding="utf-8")
    
    suggestions = generate_coach_suggestions(
        dialog_text, args.model, args.company, args.goal, 
        args.tone, args.company_info, args.constraints
    )

    # Сохранение JSON
    out_json = inp.with_suffix(".coach.json")
    out_json.write_text(json.dumps(suggestions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Подсказки (JSON): {out_json}")

    # Сохранение TXT если нужно
    if args.also_txt:
        out_txt = inp.with_suffix(".coach.txt")
        txt_content = ""
        for category, items in suggestions.items():
            txt_content += f"{category.upper()}:\n"
            for item in items:
                txt_content += f"• {item}\n"
            txt_content += "\n"
        
        out_txt.write_text(txt_content, encoding="utf-8")
        print(f"✓ Подсказки (TXT): {out_txt}")

if __name__ == "__main__":
    main()
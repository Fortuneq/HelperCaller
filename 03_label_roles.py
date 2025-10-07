# 03_label_roles.py
import argparse, json, os, sys
from pathlib import Path

try:
    # pip install openai
    from openai import OpenAI
except Exception as e:
    raise SystemExit("Не найден пакет 'openai'. Установите: pip install openai") from e


IMPORTED_OPENAI_KEY = "***REMOVED***"

SYSTEM_INSTRUCTIONS = (
    "Ты — разметчик телефонных диалогов. На входе — список сегментов расшифровки "
    "одного звонка между менеджером IT-компании «ВестКолл» и клиентом.\n\n"
    "ЗАДАНИЕ:\n"
    "1) Определи, кто произносит КАЖДУЮ реплику: Менеджер или Клиент.\n"
    "2) Объединяй соседние сегменты, если они принадлежат одному и тому же говорящему.\n"
    "3) На выходе дай ТОЛЬКО строки в формате:\n"
    "4) Если человек представляет сотурдником чего-то, кроме компании 'ВестКолл', это клиент\n"
    "   Менеджер: <текст>\n"
    "   Клиент: <текст>\n"
    "— без номеров, временных меток и пояснений. Язык — русский."
)

PROMPT_TEMPLATE = (
    "Ниже — нумерованные сегменты транскрипта (последовательность по времени). "
    "Определи говорящего для каждой реплики и верни итоговый диалог строго в формате "
    "«Менеджер: ...» / «Клиент: ...». Если роль в сегменте неочевидна — делай наиболее "
    "вероятное предположение из контекста. Объединяй подряд идущие сегменты одного говорящего.\n\n"
    "{segments_block}"
)

def load_segments(input_path: Path):
    """
    Поддерживает *.segments.json из шага 02 и, при необходимости, обычный *.txt.
    Возвращает список строк сегментов.
    """
    if input_path.suffix.lower() == ".json" and input_path.name.endswith(".segments.json"):
        data = json.loads(input_path.read_text(encoding="utf-8"))
        segs = [s.get("text","").strip() for s in data.get("segments", [])]
        segs = [t for t in segs if t]
        if not segs:
            raise SystemExit("В JSON нет сегментов.")
        return segs
    elif input_path.suffix.lower() == ".txt":
        text = input_path.read_text(encoding="utf-8").strip()
        if not text:
            raise SystemExit("Пустой .txt.")
        # Грубое разбиение на строки
        lines = [ln.strip() for ln in text.replace("?", "?\n").replace("!", "!\n").replace(".", ".\n").splitlines()]
        segs = [ln for ln in lines if ln]
        return segs
    else:
        raise SystemExit("Ожидался файл *.segments.json (из шага 02) или *.txt.")

def build_segments_block(segs):
    return "\n".join(f"[{i+1}] {s}" for i, s in enumerate(segs))

def make_client(timeout: float):
    """
    Создаёт OpenAI-клиент. Сначала пробуем импортированный ключ (из openai_key.py),
    если его нет — берём из переменной окружения OPENAI_API_KEY.
    """
    api_key = IMPORTED_OPENAI_KEY or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Не найден API-ключ.\n"
            "Создайте рядом файл openai_key.py с содержимым:\n"
            'OPENAI_API_KEY = "sk-..."\n'
            "Либо задайте переменную окружения OPENAI_API_KEY."
        )
    return OpenAI(api_key=api_key, timeout=timeout)

def call_openai(model: str, instructions: str, user_input: str, timeout: float = 120.0) -> str:
    client = make_client(timeout=timeout)
    resp = client.responses.create(
        model=model,
        instructions=instructions,
        input=user_input,
        temperature=0.2,
    )
    return resp.output_text.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="путь к *.segments.json (из 02_transcribe.py) или к *.txt")
    ap.add_argument("--model", default="gpt-4o-mini", help="модель OpenAI (напр. gpt-4o-mini / gpt-4o)")
    ap.add_argument("--out", help="путь к выходному файлу (*.dialog.txt). По умолчанию берётся из имени input.")
    args = ap.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        raise SystemExit(f"Файл не найден: {inp}")

    segs = load_segments(inp)
    segments_block = build_segments_block(segs)
    prompt = PROMPT_TEMPLATE.format(segments_block=segments_block)

    try:
        labeled = call_openai(args.model, SYSTEM_INSTRUCTIONS, prompt)
    except Exception as e:
        print(f"Ошибка обращения к OpenAI API: {e}", file=sys.stderr)
        raise SystemExit(1)

    # Путь вывода
    if args.out:
        out_path = Path(args.out)
    else:
        base = inp.with_suffix("")
        if base.name.endswith(".segments"):
            base = base.with_name(base.name.replace(".segments", ""))
        out_path = base.with_suffix(".dialog.txt")

    out_path.write_text(labeled + "\n", encoding="utf-8")
    print(f"✓ Диалог с ролями: {out_path}")

if __name__ == "__main__":
    main()

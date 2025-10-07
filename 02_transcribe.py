# 02_transcribe.py
import argparse, json
from pathlib import Path
import torch
import whisper

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", help="путь к .wav (лучше *_16k_mono.wav)")
    ap.add_argument("--model", default="large-v3", help="tiny/base/small/medium/large-v3")
    ap.add_argument("--language", default="ru")
    ap.add_argument("--threads", type=int, help="лимит потоков CPU для PyTorch (например 4)")
    args = ap.parse_args()

    if args.threads:
        torch.set_num_threads(args.threads)

    audio = Path(args.audio)
    if not audio.exists():
        raise SystemExit(f"Нет файла: {audio}")

    device = "cpu"  # ЖЁСТКО CPU
    model = whisper.load_model(args.model, device=device)
    result = model.transcribe(str(audio), language=args.language, task="transcribe", verbose=False)

    out_base = audio.with_suffix("")  # без .wav
    txt_path = out_base.with_suffix(".transcript.txt")
    json_path = out_base.with_suffix(".segments.json")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(result.get("text","").strip() + "\n")

    segs = [{"start": float(s["start"]), "end": float(s["end"]), "text": s["text"].strip()}
            for s in result.get("segments", [])]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"segments": segs, "language": result.get("language")}, f, ensure_ascii=False, indent=2)

    print(f"✓ Транскрипт: {txt_path}")
    print(f"✓ Сегменты:   {json_path}")

if __name__ == "__main__":
    main()

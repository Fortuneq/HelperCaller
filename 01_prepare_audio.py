# 01_prepare_audio.py
import argparse, subprocess, shutil
from pathlib import Path

def ensure_tool(name: str):
    if shutil.which(name) is None:
        raise SystemExit(f"Не найден '{name}'. Установите ffmpeg (он ставит и ffprobe).")

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        print(p.stdout)
        raise SystemExit(f"Command failed: {' '.join(cmd)}")
    return p.stdout.strip()

def get_channels(path: Path) -> int:
    out = run([
        "ffprobe","-v","error","-select_streams","a:0",
        "-show_entries","stream=channels","-of","default=nw=1:nk=1", str(path)
    ])
    try:
        return int(out)
    except:
        return 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="путь к исходному .mp3/.wav, напр. data/example1.mp3")
    args = ap.parse_args()

    ensure_tool("ffmpeg")
    ensure_tool("ffprobe")

    inp = Path(args.input)
    if not inp.exists():
        raise SystemExit(f"Файл не найден: {inp}")

    out_dir = inp.parent
    stem = inp.stem

    mono = out_dir / f"{stem}_16k_mono.wav"
    run(["ffmpeg","-y","-i",str(inp),"-ac","1","-ar","16000",str(mono)])
    print(f"✓ Сформирован моно-файл: {mono}")

    ch = get_channels(inp)
    print(f"Обнаружено каналов: {ch}")

    if ch >= 2:
        ch1 = out_dir / f"{stem}_ch1.wav"
        ch2 = out_dir / f"{stem}_ch2.wav"
        run([
            "ffmpeg","-y","-i",str(inp),
            "-map_channel","0.0.0","-ar","16000","-ac","1",str(ch1),
            "-map_channel","0.0.1","-ar","16000","-ac","1",str(ch2)
        ])
        print(f"✓ Разделены каналы: {ch1} / {ch2}")
    else:
        print("Запись одноканальная — для ролей используйте диаризацию (скрипт 03).")

if __name__ == "__main__":
    main()

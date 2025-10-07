# run_pipeline_slices.py
import argparse, subprocess, shutil, sys, os, json, math
from pathlib import Path
from datetime import datetime

HERE = Path(__file__).parent.resolve()

PCTS = [20, 40, 60, 70, 80]

def run(cmd, fail_hard: bool = True):
    print("→", " ".join(map(str, cmd)))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(p.stdout)
    if p.returncode != 0:
        msg = f"Команда завершилась с ошибкой ({p.returncode}): {' '.join(map(str, cmd))}"
        if fail_hard:
            raise SystemExit(msg)
        else:
            print("⚠️ " + msg, file=sys.stderr)
    return p.returncode

def safe_mkdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    return p

def make_subset_segments(full_segments_path: Path, pct: int, out_path: Path) -> int:
    data = json.loads(full_segments_path.read_text(encoding="utf-8"))
    segs = data.get("segments", [])
    total = len(segs)
    if total == 0:
        raise SystemExit(f"В {full_segments_path.name} нет сегментов.")
    n = max(1, math.ceil(total * (pct / 100.0)))
    sub = {
        "segments": segs[:n],
        "language": data.get("language"),
        "meta": {"source": full_segments_path.name, "total_segments": total, "used_segments": n, "pct": pct}
    }
    out_path.write_text(json.dumps(sub, ensure_ascii=False, indent=2), encoding="utf-8")
    return n

def build_combined_txt(dialog_file: Path, coach_txt_file: Path, out_path: Path):
    dialog_text = dialog_file.read_text(encoding="utf-8") if dialog_file.exists() else ""
    coach_text = coach_txt_file.read_text(encoding="utf-8") if coach_txt_file and coach_txt_file.exists() else ""
    header = (
        "================= ДИАЛОГ =================\n"
        f"(источник: {dialog_file.name if dialog_file.exists() else '—'})\n\n"
    )
    header2 = (
        "\n\n================ ПОДСКАЗКИ ================\n"
        f"(источник: {coach_txt_file.name if (coach_txt_file and coach_txt_file.exists()) else '—'})\n\n"
    )
    out_path.write_text(header + dialog_text + header2 + coach_text, encoding="utf-8")

def check_env():
    if not os.environ.get("OPENAI_API_KEY"):
        # для демо с хардкодом в 04 это не критично, просто предупреждение
        print("⚠️ OPENAI_API_KEY не задан — ок для демо, т.к. ключ захардкожен в 04.", file=sys.stderr)

def main():
    ap = argparse.ArgumentParser(description="Полный пайплайн 01→04 с разбиением на 20/40/60/70/80% по сегментам")
    ap.add_argument("--input", default="data/example_for_split.mp3", help="входной .mp3/.wav (по умолчанию data/example_for_split.mp3)")
    ap.add_argument("--language", default="ru", help="язык для Whisper (напр. ru)")
    ap.add_argument("--asr-model", default="large-v3", help="модель Whisper (tiny/base/small/medium/large-v3)")
    ap.add_argument("--threads", type=int, help="лимит потоков CPU для шага 02 (опционально)")
    ap.add_argument("--coach-model", default="gpt-4o-mini", help="модель OpenAI для шагов 03 и 04")
    ap.add_argument("--goal", default="привлечь клиента и продать ему наши услуги",
                    help="целевое действие для шага 04")
    ap.add_argument("--company", default="ВестКолл", help="для шага 04: имя компании")
    ap.add_argument("--tone", default="дружелюбный, экспертный, без давления", help="для шага 04: тональность")
    ap.add_argument("--company-info", default="", help="для шага 04: УТП/кейсы/продукты (по желанию)")
    ap.add_argument("--constraints", default="", help="для шага 04: ограничения бренда")
    ap.add_argument("--outdir", help="корневая папка результатов (по умолчанию outputs/<stem>_<timestamp>)")
    ap.add_argument("--skip-coach", action="store_true", help="не вызывать шаг 04 (только диалоги)")
    args = ap.parse_args()

    check_env()

    inp = Path(args.input).resolve()
    if not inp.exists():
        raise SystemExit(f"Файл не найден: {inp}")

    stem = inp.stem
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    root_out = Path(args.outdir) if args.outdir else HERE / "outputs" / f"{stem}_{ts}"
    safe_mkdir(root_out)
    print(f"📁 Корневая папка результатов: {root_out}")

    rc = run([sys.executable, str(HERE / "01_prepare_audio.py"), str(inp)])
    if rc != 0:
        raise SystemExit("Шаг 01 завершился с ошибкой.")

    mono_wav = inp.with_name(f"{stem}_16k_mono.wav")
    if not mono_wav.exists():
        raise SystemExit("Не найден моно-файл после шага 01: " + str(mono_wav))

    cmd_02 = [sys.executable, str(HERE / "02_transcribe.py"), str(mono_wav), "--language", args.language, "--model", args.asr_model]
    if args.threads:
        cmd_02 += ["--threads", str(args.threads)]
    rc = run(cmd_02)
    if rc != 0:
        raise SystemExit("Шаг 02 завершился с ошибкой.")

    base_no_ext = mono_wav.with_suffix("")
    transcript_txt = base_no_ext.with_suffix(".transcript.txt")
    segments_json = base_no_ext.with_suffix(".segments.json")
    if not segments_json.exists():
        raise SystemExit("Не найден файл сегментов после шага 02: " + str(segments_json))

    for p in [mono_wav, transcript_txt, segments_json]:
        if p.exists():
            shutil.copy2(p, root_out / p.name)

    for pct in PCTS:
        print(f"\n=== Обработка {pct}% ===")
        subdir = safe_mkdir(root_out / f"{pct}")
        subset_segments = subdir / f"{stem}_16k_mono.p{pct}.segments.json"
        used = make_subset_segments(segments_json, pct, subset_segments)
        print(f"✓ Создан срез {pct}%: {used} сегментов → {subset_segments.name}")

        rc = run([sys.executable, str(HERE / "03_label_roles.py"), str(subset_segments), "--model", args.coach_model])
        if rc != 0:
            print(f"⚠️ Пропускаю шаги 04/сборку для {pct}% из-за ошибки на шаге 03.", file=sys.stderr)
            continue

        base = subset_segments.with_suffix("")
        dialog_txt = base.with_suffix(".dialog.txt")
        if not dialog_txt.exists():
            candidates = list(subdir.glob("*.dialog.txt"))
            if candidates:
                dialog_txt = candidates[0]
        if not dialog_txt.exists():
            print(f"⚠️ Не найден файл диалога для {pct}%: {dialog_txt}", file=sys.stderr)
            continue

        coach_txt = None
        if not args.skip_coach:
            cmd_04 = [
                sys.executable, str(HERE / "04_coach_replies.py"), str(dialog_txt),
                "--model", args.coach_model,
                "--company", args.company,
                "--goal", args.goal,
                "--tone", args.tone,
                "--also-txt"
            ]
            if args.company_info:
                cmd_04 += ["--company-info", args.company_info]
            if args.constraints:
                cmd_04 += ["--constraints", args.constraints]

            rc = run(cmd_04, fail_hard=False)
            if rc == 0:
                coach_txt = dialog_txt.with_suffix(".coach.txt")
                if not coach_txt.exists():
                    cands = sorted(subdir.glob("*.coach.txt"))
                    coach_txt = cands[0] if cands else None
            else:
                print(f"⚠️ Шаг 04 для {pct}% завершился с ошибкой, продолжу без подсказок.", file=sys.stderr)

        combined = subdir / f"{stem}_p{pct}_coach_with_dialog.txt"
        try:
            build_combined_txt(dialog_txt, coach_txt, combined)
            print(f"✓ Итоговый TXT ({pct}%): {combined.name}")
        except Exception as e:
            print(f"⚠️ [{pct}%] Не удалось собрать общий TXT: {e}", file=sys.stderr)

    print("\n✅ Готово!")
    print("Все результаты разложены по подпапкам:", ", ".join(map(str, PCTS)))
    print(root_out)

if __name__ == "__main__":
    main()

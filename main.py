#!/usr/bin/env python3
"""
HelperCaller - ;02=K9 D09; 4;O 70?CA:0 ?09?;09=0 ?>4A:07>:
#?@>I5==K9 8=B5@D59A 4;O helper_caller_pipeline.py
"""

import sys
from pathlib import Path
from helper_caller_pipeline import HelperCallerPipeline

def main():
    print("<¯ HelperCaller - !8AB5<0 ?>4A:07>: 4;O ?@>406")
    print("=" * 50)
    
    # @>25@:0 0@3C<5=B>2
    if len(sys.argv) < 2:
        print("A?>;L7>20=85:")
        print("  python main.py audio_file.wav")
        print("  python main.py --realtime")
        print("\n@8<5@K:")
        print("  python main.py data/example1.mp3")
        print("  python main.py --realtime")
        sys.exit(1)
    
    # !>740=85 ?09?;09=0 A >?B8<0;L=K<8 =0AB@>9:0<8
    pipeline = HelperCallerPipeline(
        whisper_model="base",  # KAB@0O <>45;L 4;O @50;L=>3> 2@5<5=8
        openai_model="gpt-4o-mini",  # KAB@0O <>45;L OpenAI
        company="5AB>;;",
        goal="?@82;5GL :;85=B0 8 ?@>40BL CA;C38",
        tone="4@C65;N1=K9, M:A?5@B=K9, 157 402;5=8O",
        company_info="1;0G=0O B5;5D>=8O, ><=8:0=0;L=K5 :>=B0:B-F5=B@K, 8=B53@0F88 A CRM",
        constraints="=5 >15I0BL A:84:8 157 A>3;0A>20=8O",
        language="ru"
    )
    
    try:
        if sys.argv[1] == "--realtime":
            print("0?CA: 2 @568<5 @50;L=>3> 2@5<5=8...")
            pipeline.run_realtime_mode()
        else:
            #  568< D09;0
            audio_file = Path(sys.argv[1])
            if not audio_file.exists():
                print(f"H81:0: D09; =5 =0945= - {audio_file}")
                sys.exit(1)
            
            print(f"1@010BK20N D09;: {audio_file}")
            results = pipeline.run_file_mode(audio_file)
            
            # !>E@0=5=85 @57C;LB0B>2
            output_dir = audio_file.parent / f"{audio_file.stem}_results"
            pipeline.save_results(output_dir, results)
            
            print(f"\n >B>2>! 1@01>B0=> {results['total_segments']} A53<5=B>2")
            
    except KeyboardInterrupt:
        print("\n  AB0=>2;5=> ?>;L7>20B5;5<")
    except Exception as e:
        print(f"L H81:0: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
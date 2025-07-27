import cv2
import numpy as np
import pandas as pd
from demoparser2 import DemoParser
import sys
import os
import subprocess
import multiprocessing
import time
from argparse import ArgumentParser
import traceback

def get_round_timings(parser: DemoParser):
    print("Parsing game events to identify rounds...")
    try:
        event_data_tuples = parser.parse_events(["round_start", "round_end"])
        if not event_data_tuples:
            print("Warning: parse_events returned an empty list. No rounds found.")
            return []
        all_events_list = []
        for event_name, event_df in event_data_tuples:
            event_df['event_name'] = event_name
            all_events_list.append(event_df)
        events_df = pd.concat(all_events_list, ignore_index=True)
        events_df = events_df.sort_values(by='tick').reset_index(drop=True)
    except Exception as e:
        print(f"Could not parse round events. The demo may be corrupted or partial. Error: {e}"); traceback.print_exc(); return []
    round_timings = []
    start_tick = None
    for _, row in events_df.iterrows():
        if row['event_name'] == 'round_start': start_tick = row['tick']
        elif row['event_name'] == 'round_end' and start_tick is not None:
            round_timings.append((start_tick, row['tick'])); start_tick = None
    print(f"Identified {len(round_timings)} complete rounds in the demo.")
    return round_timings

def generate_video_chunk(ticks_df, output_path, tickrate):
    """Generates a video clip by resampling tick data to a fixed FPS."""
    if ticks_df.empty:
        return None

    width, height = (400, 410)
    fps = 60
    
    fourcc = cv2.VideoWriter_fourcc(*'FFV1')
    video = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    if not video.isOpened():
        raise IOError(f"FATAL: Could not open video writer for {output_path}")

    BG_COLOR, KEY_OFF, KEY_ON, TEXT_ON, TEXT_OFF = (0, 255, 0), (0, 0, 0), (255, 255, 255), (0, 0, 0), (200, 200, 200)
    
    key_layout = {
        'W': (110, 30, 60, 60), 'E': (180, 30, 60, 60),
        'A': (40, 100, 60, 60), 'S': (110, 100, 60, 60), 'D': (180, 100, 60, 60),
        'SHIFT': (20, 170, 150, 60),
        'CTRL': (20, 240, 70, 60),
        'SPACE': (100, 240, 140, 60),
        'LMB': (20, 310, 100, 60),
        'RMB': (130, 310, 110, 60)
    }

    start_tick = ticks_df['tick'].min()
    end_tick = ticks_df['tick'].max()
    duration_seconds = (end_tick - start_tick) / tickrate
    total_frames = int(duration_seconds * fps)
    
    ticks_df = ticks_df.set_index('tick')

    for frame_index in range(total_frames):
        current_time_in_clip = frame_index / fps
        target_tick = start_tick + int(current_time_in_clip * tickrate)
        
        try:
            row = ticks_df.asof(target_tick)
        except KeyError:
            continue

        frame = np.full((height, width, 3), BG_COLOR, dtype=np.uint8)
        
        is_jump_event = (
            row.get('is_airborne', False) and
            not row.get('was_airborne', False) and
            row.get('velocity_Z', 0) > 1
        )
        key_states = {
            'W': row.get('FORWARD', False), 'A': row.get('LEFT', False), 'S': row.get('BACK', False),
            'D': row.get('RIGHT', False), 'SHIFT': row.get('is_walking', False),
            'E': row.get('USE', False), 'CTRL': row.get('duck_amount', 0.0) > 0.95,
            'SPACE': is_jump_event,
            'LMB': row.get('FIRE', False),
            'RMB': row.get('RIGHTCLICK', False)
        }

        for key, pos in key_layout.items():
            x, y, w, h = pos; is_pressed = key_states.get(key, False); color = KEY_ON if is_pressed else KEY_OFF
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, -1); cv2.rectangle(frame, (x, y), (x+w, y+h), (100, 100, 100), 2)
            text_c = TEXT_ON if is_pressed else TEXT_OFF; text_size = cv2.getTextSize(key, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            cv2.putText(frame, key, (x + (w - text_size[0]) // 2, y + (h + text_size[1]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, text_c, 2)
        
        video.write(frame)
    video.release()
    return output_path

def parallel_video_creation(ticks_df, base_output_path, num_processes, ffmpeg_codec, tickrate):
    """Generates a single video for keyboard and mouse states."""
    if ticks_df.empty:
        print(f"INFO: No player actions in this timeframe for {os.path.basename(base_output_path)}. Skipping.")
        return

    print("Generating keyboard and mouse overlay video...")
    temp_file = f"temp_keyboard_and_mouse_{time.time()}.avi"
    
    generated_file = generate_video_chunk(ticks_df, temp_file, tickrate)

    if generated_file:
        final_path = f"{base_output_path}.mp4"
        print(f"Encoding final video to {os.path.basename(final_path)}...")
        ffmpeg_command = ['ffmpeg', '-i', generated_file, '-c:v', ffmpeg_codec, '-y', final_path]
        subprocess.run(ffmpeg_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(generated_file):
            os.remove(generated_file)

# --- Main execution block ---
if __name__ == '__main__':
    parser = ArgumentParser(description="Generate keystroke overlays from CS2 demo files.")
    parser.add_argument("demo_path", help="Path to the .dem file.")
    parser.add_argument("player_name", help="The exact in-game name of the player.")
    parser.add_argument("output_base_path", help="Base path and name for the final output video (e.g., 'C:\\videos\\my_video').")
    parser.add_argument("-p", "--processes", type=int, default=os.cpu_count(), help=f"Number of processes to use. Defaults to all available CPU cores ({os.cpu_count()}).")
    parser.add_argument("--ffmpeg-codec", type=str, default="libx264", help="The FFmpeg codec for the FINAL output. Default: 'libx24'.")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("-r", "--rounds", type=str, default=None, help="Comma-separated list of round numbers to generate.")
    mode_group.add_argument("--ticks", type=str, help="A specific tick range to generate a video for. Format: 'START,END'.")

    # --- MODIFICATION: Set default=64 for the tickrate argument ---
    parser.add_argument("--tickrate", type=int, default=64, help="The tickrate of the demo file (e.g., 64 or 128). Defaults to 64.")

    args = parser.parse_args()

    # --- MODIFICATION: Simplified logic, as tickrate always has a value ---
    # If no specific mode is chosen, default to processing all rounds.
    if not args.ticks and not args.rounds:
        args.rounds = "all"

    output_dir = os.path.dirname(args.output_base_path)
    if output_dir and not os.path.exists(output_dir): os.makedirs(output_dir)

    main_start_time = time.time()
    try:
        print("--- Parsing Ticks for Player Actions (this may take a moment) ---")
        tick_parser = DemoParser(args.demo_path)
        
        all_ticks_df = tick_parser.parse_ticks(
            wanted_props=["FORWARD", "LEFT", "RIGHT", "BACK", "FIRE", "RIGHTCLICK", 
                          "USE", "is_walking", "duck_amount", "is_airborne", "velocity_Z", "tick", "name"]
        )
        del tick_parser

        player_ticks_df = all_ticks_df[all_ticks_df['name'] == args.player_name].copy()
        if player_ticks_df.empty:
            print(f"Error: No data found for player '{args.player_name}'. Please check the name for case sensitivity.")
            sys.exit(1)

        player_ticks_df['was_airborne'] = player_ticks_df['is_airborne'].shift(1).fillna(False)

        if args.ticks:
            print("\n--- Processing in Tick Range Mode ---")
            try:
                parts = args.ticks.split(',')
                if len(parts) != 2: raise ValueError("Tick format must be START,END")
                start_tick = int(parts[0])
                end_tick = int(parts[1]) if parts[1] else player_ticks_df['tick'].max()
                if start_tick >= end_tick: raise ValueError("Start tick must be less than end tick.")
            except (ValueError, IndexError) as e:
                print(f"Error: Invalid format for --ticks. {e}. Please use 'START,END'."); sys.exit(1)

            print(f"Processing from tick {start_tick} to {end_tick} with a tickrate of {args.tickrate}...")
            tick_range_df = player_ticks_df[(player_ticks_df['tick'] >= start_tick) & (player_ticks_df['tick'] <= end_tick)]
            output_base_for_range = f"{args.output_base_path}_ticks_{start_tick}_to_{end_tick}"
            parallel_video_creation(tick_range_df, output_base_for_range, args.processes, args.ffmpeg_codec, args.tickrate)
            print(f"\n✅ Finished processing specified tick range.")

        else: # Round-based processing
            print("\n--- Processing in Round-Based Mode ---")
            event_parser = DemoParser(args.demo_path)
            round_timings = get_round_timings(event_parser)
            del event_parser

            if not round_timings: print("Could not find any rounds to process. Exiting."); sys.exit(1)

            requested_rounds_set = set(args.rounds.split(',')) if args.rounds != 'all' else {'all'}
            rounds_to_process = []
            for i, (start_tick, end_tick) in enumerate(round_timings):
                round_num = i + 1
                if 'all' in requested_rounds_set or str(round_num) in requested_rounds_set:
                    rounds_to_process.append((round_num, start_tick, end_tick))
            
            if not rounds_to_process: print("None of the requested rounds were found in the demo. Exiting."); sys.exit(1)

            total_rounds = len(rounds_to_process)
            for count, (round_num, start_tick, end_tick) in enumerate(rounds_to_process, 1):
                round_start_time = time.time()
                print(f"\n--- Processing Round {round_num} ({count}/{total_rounds}) ---")
                round_df = player_ticks_df[(player_ticks_df['tick'] >= start_tick) & (player_ticks_df['tick'] <= end_tick)]
                output_base_for_round = f"{args.output_base_path}_round_{round_num:02d}"
                parallel_video_creation(round_df, output_base_for_round, args.processes, args.ffmpeg_codec, args.tickrate)
                print(f"--- Finished Round {round_num} in {time.time() - round_start_time:.2f} seconds ---")

            print(f"\n✅ Finished processing {total_rounds} requested round(s).")
        
        print(f"Total time taken: {time.time() - main_start_time:.2f} seconds.")
        
    except Exception:
        print(f"\nAn unexpected error occurred:"); traceback.print_exc()
    finally:
        import glob; print("Cleaning up temporary files...")
        for f in glob.glob("temp_*.avi"):
            if os.path.exists(f): os.remove(f)
        for f in glob.glob("temp_filelist_*.txt"):
            if os.path.exists(f): os.remove(f)
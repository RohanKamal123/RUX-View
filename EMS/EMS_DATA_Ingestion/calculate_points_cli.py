from point_system import mz_media_points

def run_cli():
    print("--- Media Points Calculator ---")
    print("Please provide the following details to calculate media points.")

    # Get video_type
    while True:
        video_type_input = input("Video Type (Short/Long): ").strip().lower()
        if video_type_input in ["short", "long"]:
            break
        else:
            print("Invalid input. Video Type must be 'Short' or 'Long'.")

    # Get editing_style
    while True:
        editing_style_input = input("Editing Style (Low/Medium/High): ").strip().lower()
        if editing_style_input in ["low", "medium", "high"]:
            break
        else:
            print("Invalid input. Editing Style must be 'Low', 'Medium', or 'High'.")

    # Get difficulty
    while True:
        difficulty_input = input("Difficulty (Low/Medium/High): ").strip().lower()
        if difficulty_input in ["low", "medium", "high"]:
            break
        else:
            print("Invalid input. Difficulty must be 'Low', 'Medium', or 'High'.")

    # Get duration
    while True:
        try:
            duration_input = float(input("Duration in minutes (e.g., 0.5, 6.0): ").strip())
            if duration_input > 0:
                break
            else:
                print("Duration must be a positive number.")
        except ValueError:
            print("Invalid input. Duration must be a number.")

    # Get no_of_videos
    while True:
        try:
            no_of_videos_input = int(input("Number of Videos (default: 1): ").strip() or "1")
            if no_of_videos_input > 0:
                break
            else:
                print("Number of videos must be a positive integer.")
        except ValueError:
            print("Invalid input. Number of Videos must be an integer.")

    # Get simple_batch
    while True:
        simple_batch_input = input("Simple Batch (True/False, default: False): ").strip().lower()
        if simple_batch_input == "":
            simple_batch_bool = False
            break
        elif simple_batch_input in ["true", "false"]:
            simple_batch_bool = simple_batch_input == "true"
            break
        else:
            print("Invalid input. Simple Batch must be 'True' or 'False'.")

    try:
        points = mz_media_points(
            video_type=video_type_input,
            editing_style=editing_style_input,
            difficulty=difficulty_input,
            duration=duration_input,
            no_of_videos=no_of_videos_input,
            simple_batch=simple_batch_bool
        )
        print(f"\nCalculated Media Points: {points}")
    except ValueError as e:
        print(f"\nError calculating points: {e}")

if __name__ == "__main__":
    run_cli()

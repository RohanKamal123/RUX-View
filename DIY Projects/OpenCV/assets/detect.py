import cv2
from ultralytics import YOLO

# Replace with your phone's IP
CAMERA_URL = "http://192.168.1.136:8080/video"

# Load YOLOv8 nano model (downloads automatically ~6MB first run)
model = YOLO("yolov8n.pt")

cap = cv2.VideoCapture(CAMERA_URL)

if not cap.isOpened():
    print("❌ Cannot connect to camera.")
    exit()

print("✅ Detection running! Press Q to quit.")

while True:
    ret, frame = cap.read()
    # Add this right after cap.read()
    frame = cv2.resize(frame, (640, 480))
    if not ret:
        print("❌ Frame read failed.")
        break

    # Run detection — only care about class 0 (person)
    results = model(frame, classes=[0], verbose=False)

    # How many people detected this frame
    person_count = len(results[0].boxes)

    # Draw bounding boxes on frame
    annotated_frame = results[0].plot()

    # Show count on screen
    cv2.putText(
        annotated_frame,
        f"People detected: {person_count}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2
    )

    cv2.imshow("CCTV - Person Detection", annotated_frame)

    if person_count > 0:
        print(f"🚨 {person_count} person(s) detected!")

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
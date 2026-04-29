import cv2

# Replace with your phone's IP
CAMERA_URL = "http://192.168.1.136:8080/video"

cap = cv2.VideoCapture(CAMERA_URL)

if not cap.isOpened():
    print("❌ Cannot connect to camera. Check IP and WiFi.")
    exit()

print("✅ Camera connected! Press Q to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Failed to read frame.")
        break

    cv2.imshow("CCTV Feed", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
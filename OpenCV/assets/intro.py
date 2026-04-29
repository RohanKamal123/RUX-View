import cv2

img = cv2.imread('assets/rohan.jpg', cv2.IMREAD_COLOR)
if img is None:
    print("Error: Could not load image.")
    exit() 
cv2.imshow('image', img)
cv2.waitKey(0)
cv2.destroyAllWindows()

import cv2

cap=cv2.VideoCapture('assets/hudai.mp4')  
success,img=cap.read()

while success:
    cv2.imshow('Video',img)
    if cv2.waitKey(15) & 0xFF==27 :  # wait for 15 ms
        break
    success,img=cap.read()
cap.release()
cv2.destroyAllWindows('Video')

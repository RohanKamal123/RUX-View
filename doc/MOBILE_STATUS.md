# Mobile Apps — Development Status

## Android (Kotlin)
Status: Feature-complete UI — all core screens built.
Files: 11 files, ~2,400 lines
Screens: Login, Camera List, Event Feed, Event Detail,
         Person Profile, Settings
Services: FCM push notifications (VisionOSMessagingService)
API: Full REST client (ApiClient + VisionOSApi)
Remaining: End-to-end testing against production backend,
           Play Store packaging

## iOS (Swift)
Status: Feature-complete UI — all core screens built.
Files: 8 files, ~1,400 lines  
Screens: Login, Camera List, Event Feed, Event Detail,
         Person Profile, Settings
API: Full REST client (VisionOSApiService)
Remaining: End-to-end testing against production backend,
           App Store packaging, push notification setup

## Summary
Both platforms have equivalent screen coverage.
Neither is scaffold. Both need backend integration 
testing before store submission.
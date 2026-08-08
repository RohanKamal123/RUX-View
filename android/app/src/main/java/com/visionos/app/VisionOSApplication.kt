package com.visionos.app

import android.app.Application
import com.google.firebase.FirebaseApp

class VisionOSApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        FirebaseApp.initializeApp(this)
    }
}

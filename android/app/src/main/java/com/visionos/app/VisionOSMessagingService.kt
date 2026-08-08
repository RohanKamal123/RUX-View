package com.visionos.app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class VisionOSMessagingService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "VisionOSFCM"
        private const val CHANNEL_EMERGENCY = "emergency"
        private const val CHANNEL_ALERTS = "alerts"
        private const val CHANNEL_DIGEST = "digest"
        private const val NOTIFICATION_ID_BASE = 1000
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.d(TAG, "New FCM token: $token")
        // Send token to backend
        CoroutineScope(Dispatchers.IO).launch {
            try {
                // TODO: Implement API call to register token with backend
                // VisionOSApi.registerFcmToken(token)
                Log.d(TAG, "Token sent to backend")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send token to backend", e)
            }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        Log.d(TAG, "Message received: ${message.messageId}")

        val notificationType = message.data["type"] ?: "alert"
        val eventId = message.data["event_id"]?.toIntOrNull()
        val cameraName = message.data["camera_name"] ?: "Unknown Camera"
        val threatLevel = message.data["threat_level"] ?: "LOW"
        val body = message.data["body"] ?: message.notification?.body ?: "New event detected"

        // Build notification title
        val title = when (threatLevel) {
            "EMERGENCY" -> "VisionOS EMERGENCY - $cameraName"
            "HIGH" -> "VisionOS HIGH - $cameraName"
            else -> "VisionOS - $cameraName"
        }

        // Determine channel and priority
        val channelId = when (threatLevel) {
            "EMERGENCY" -> CHANNEL_EMERGENCY
            "HIGH" -> CHANNEL_ALERTS
            else -> CHANNEL_ALERTS
        }

        val priority = when (threatLevel) {
            "EMERGENCY" -> NotificationCompat.PRIORITY_MAX
            "HIGH" -> NotificationCompat.PRIORITY_HIGH
            else -> NotificationCompat.PRIORITY_DEFAULT
        }

        // Create intent to open EventDetailScreen
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("navigate_to", "event_detail")
            putExtra("event_id", eventId)
            putExtra("threat_level", threatLevel)
        }

        val pendingIntent = PendingIntent.getActivity(
            this,
            eventId ?: 0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // Build notification
        val notification = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText(body)
            .setPriority(priority)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .build()

        // Show notification
        val notificationId = (eventId ?: (System.currentTimeMillis() % Int.MAX_VALUE).toInt())
        try {
            NotificationManagerCompat.from(this).notify(notificationId, notification)
        } catch (e: SecurityException) {
            Log.e(TAG, "Notification permission not granted", e)
        }
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

            // Emergency channel (highest priority)
            val emergencyChannel = NotificationChannel(
                CHANNEL_EMERGENCY,
                "Emergency Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Critical emergency alerts requiring immediate attention"
                enableVibration(true)
                setSound(
                    android.provider.Settings.System.DEFAULT_NOTIFICATION_URI,
                    android.media.AudioAttributes.Builder()
                        .setUsage(android.media.AudioAttributes.USAGE_ALARM)
                        .build()
                )
                enableLights(true)
                setLightColor(android.graphics.Color.RED)
            }
            notificationManager.createNotificationChannel(emergencyChannel)

            // Alerts channel (normal priority)
            val alertsChannel = NotificationChannel(
                CHANNEL_ALERTS,
                "Security Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Security alerts for detected events"
                enableVibration(true)
            }
            notificationManager.createNotificationChannel(alertsChannel)

            // Digest channel (low priority)
            val digestChannel = NotificationChannel(
                CHANNEL_DIGEST,
                "Daily Digest",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Daily summary of events"
                setSound(null, null)
                enableVibration(false)
            }
            notificationManager.createNotificationChannel(digestChannel)
        }
    }
}

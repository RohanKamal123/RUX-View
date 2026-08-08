package com.visionos.app

import com.google.gson.annotations.SerializedName
import retrofit2.http.*

// Mirrors backend/api/cameras.py's GET /api/cameras response shape exactly
// -- the previous locationName/status/lastEventTime/unreadAlertCount
// fields didn't exist on that endpoint at all (no location-name
// resolution, no computed online/offline status, no last-event lookup, no
// unread-alert tracking anywhere in the backend), so Gson would silently
// leave them null and any UI code reading them would NPE at runtime.
data class CameraSummary(
    val id: String,
    val name: String,
    val mode: String,
    val enabled: Boolean,
    @SerializedName("rtsp_url") val rtspUrl: String?,
    @SerializedName("connection_type") val connectionType: String,
    @SerializedName("p2p_serial") val p2pSerial: String?,
    @SerializedName("p2p_username") val p2pUsername: String?,
    @SerializedName("rtmp_push_url") val rtmpPushUrl: String?,
    @SerializedName("created_at") val createdAt: String?,
    @SerializedName("last_seen_at") val lastSeenAt: String?
)

data class CamerasResponse(
    val cameras: List<CameraSummary>,
    val total: Int
)

data class CreateCameraRequest(
    val name: String,
    val mode: String = "indoor",
    @SerializedName("connection_type") val connectionType: String = "rtsp",
    @SerializedName("rtsp_url") val rtspUrl: String? = null,
    @SerializedName("p2p_serial") val p2pSerial: String? = null,
    @SerializedName("p2p_username") val p2pUsername: String? = null,
    @SerializedName("p2p_password") val p2pPassword: String? = null
)

data class CreateCameraResponse(
    val id: String,
    val status: String,
    @SerializedName("connection_type") val connectionType: String,
    @SerializedName("rtmp_push_url") val rtmpPushUrl: String?
)

data class EventItem(
    val id: Int,
    val cameraName: String,
    val threatLevel: String,  // LOW/MEDIUM/HIGH/EMERGENCY
    val timestamp: String,
    val thumbnailUrl: String?,
    val description: String?,
    val durationSec: Float?,
    val personIds: List<String>?
)

data class EventDetail(
    val id: Int,
    val cameraName: String,
    val cameraId: String,
    val threatLevel: String,
    val timestampStart: String,
    val timestampEnd: String?,
    val durationSec: Float?,
    val thumbnailUrl: String?,
    val description: String?,
    val gemmaAnalysis: String?,
    val geminiDecision: String?,
    val personIds: List<String>?,
    val audioTranscript: String?,
    val audioInterpretation: String?
)

data class PersonProfile(
    val personUid: String,
    val firstSeen: String?,
    val lastSeen: String?,
    val sightingCount: Int,
    val threatFlags: Int,
    val isStaff: Boolean,
    val userLabel: String?,
    val camerasSeen: List<String>,
    val sightings: List<SightingItem>
)

data class SightingItem(
    val eventId: Int,
    val cameraName: String,
    val timestamp: String,
    val thumbnailUrl: String?,
    val clothingDescription: String?
)

data class AppSettings(
    val notificationsEnabled: Boolean,
    val highAlertVibration: Boolean,
    val emergencyAlertSound: Boolean,
    val digestTime: String,  // "22:00"
    val theme: String  // "system" / "light" / "dark"
)

interface VisionOSApi {
    @GET("api/events")
    suspend fun getEvents(
        @Query("camera_id") cameraId: String? = null,
        @Query("threat_level") threatLevel: String? = null,
        @Query("limit") limit: Int = 20,
        @Query("offset") offset: Int = 0
    ): List<EventItem>

    @GET("api/events/{id}")
    suspend fun getEventDetail(@Path("id") eventId: Int): EventDetail

    @GET("api/cameras")
    suspend fun getCameras(): CamerasResponse

    @POST("api/cameras")
    suspend fun createCamera(@Body request: CreateCameraRequest): CreateCameraResponse

    @GET("api/persons/{uid}")
    suspend fun getPersonProfile(@Path("uid") personUid: String): PersonProfile

    @PUT("api/persons/{uid}/label")
    suspend fun updatePersonLabel(
        @Path("uid") personUid: String,
        @Body label: Map<String, String>
    )

    @GET("api/settings")
    suspend fun getSettings(): AppSettings

    @PUT("api/settings")
    suspend fun updateSettings(@Body settings: AppSettings)
}

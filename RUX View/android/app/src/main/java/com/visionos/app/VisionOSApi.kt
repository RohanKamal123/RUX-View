package com.visionos.app

import retrofit2.http.*

data class CameraSummary(
    val id: String,
    val name: String,
    val locationName: String,
    val mode: String,
    val status: String,  // online/offline/error
    val lastEventTime: String?,
    val unreadAlertCount: Int = 0
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
    suspend fun getCameras(): List<CameraSummary>

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

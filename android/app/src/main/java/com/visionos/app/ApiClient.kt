package com.visionos.app

import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Singleton Retrofit client for Vision OS backend API.
 *
 * Points to the production Cloud Run instance.
 * All API calls go through Firebase Auth token in the Authorization header.
 */
object ApiClient {

    // ── Production Cloud Run URL (service: visionos-backend, us-central1,
    //    project rux-view-497104 -- the only live backend as of the Aug 2026
    //    consolidation; two other stale services, vision-os and visionos,
    //    were deleted for leaking real credentials in plaintext env vars) ──
    private const val BASE_URL = "https://visionos-backend-1004956364101.us-central1.run.app/"

    private val authInterceptor = Interceptor { chain ->
        val original = chain.request()
        val token = FirebaseAuthTokenProvider.getToken()
        val request = if (token != null) {
            original.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            original
        }
        chain.proceed(request)
    }

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = if (BuildConfig.DEBUG) {
            HttpLoggingInterceptor.Level.BODY
        } else {
            HttpLoggingInterceptor.Level.NONE
        }
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private val retrofit: Retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    val api: VisionOSApi = retrofit.create(VisionOSApi::class.java)
}

/**
 * Provides the current Firebase ID token for API authentication.
 * Runs synchronously on the calling thread (should be background thread).
 */
object FirebaseAuthTokenProvider {
    private var cachedToken: String? = null
    private var tokenExpiry: Long = 0L

    fun getToken(): String? {
        // Return cached token if still valid (within 5 min of expiry)
        if (cachedToken != null && System.currentTimeMillis() < tokenExpiry - 300_000) {
            return cachedToken
        }

        val user = com.google.firebase.auth.FirebaseAuth.getInstance().currentUser ?: return null

        // Use a semaphore to make the async call synchronous
        val semaphore = java.util.concurrent.Semaphore(0)
        var result: String? = null

        user.getIdToken(false)
            .addOnSuccessListener { tokenResult ->
                cachedToken = tokenResult.token
                // GetTokenResult.expirationTimestamp is in SECONDS since
                // epoch, not millis -- there's no ...Millis variant.
                tokenExpiry = tokenResult.expirationTimestamp * 1000
                result = cachedToken
                semaphore.release()
            }
            .addOnFailureListener {
                semaphore.release()
            }

        semaphore.acquire()
        return result
    }
}

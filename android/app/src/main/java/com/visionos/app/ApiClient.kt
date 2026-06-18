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

    // ── Production Cloud Run URL ──────────────────────────────
    private const val BASE_URL = "https://visionos-1004956364101.asia-south1.run.app/"

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
                tokenExpiry = tokenResult.expirationTimestampMillis
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

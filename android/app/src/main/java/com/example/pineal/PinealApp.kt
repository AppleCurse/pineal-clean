package com.example.pineal

import android.app.Application
import com.example.pineal.data.local.PinealDatabase
import com.example.pineal.data.local.PinealRepository

class PinealApp : Application() {
    lateinit var repository: PinealRepository
        private set

    override fun onCreate() {
        super.onCreate()
        val db = PinealDatabase.getInstance(this)
        repository = PinealRepository(db.analysisDao(), db.reconDao())
    }
}

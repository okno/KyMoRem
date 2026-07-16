plugins {
    id("com.android.application")
}

android {
    namespace = "dev.kymorem.android"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.kymorem.android"
        minSdk = 23
        targetSdk = 35
        versionCode = 1
        versionName = "0.2.0-rc2"
    }

    splits {
        abi {
            isEnable = true
            reset()
            include("armeabi-v7a", "arm64-v8a", "x86", "x86_64")
            isUniversalApk = true
        }
    }
}

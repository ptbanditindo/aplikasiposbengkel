import org.gradle.api.tasks.bundling.Zip

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// Backend Python diambil apa adanya dari root repo, dibungkus jadi asset ZIP
// agar bisa diekstrak saat aplikasi pertama kali berjalan.
val backendAssetsDir = layout.buildDirectory.dir("generated/backendAssets")

val packageBackend by tasks.registering(Zip::class) {
    val repoRoot = rootProject.projectDir.parentFile
    archiveFileName.set("bengkel_backend.zip")
    destinationDirectory.set(backendAssetsDir)
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
    from(repoRoot) {
        include("config.py")
        include("api/**")
        include("services/**")
        include("repositories/**")
        include("database/**")
        include("frontend/**")
        exclude("**/__pycache__/**")
        exclude("**/*.pyc")
    }
}

android {
    namespace = "com.bengkelpos.radiator"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.bengkelpos.radiator"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "2.0.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }
    }

    sourceSets {
        getByName("main") {
            assets.srcDir(backendAssetsDir)
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

chaquopy {
    defaultConfig {
        version = "3.10"
        // Semua dependensi didaftarkan eksplisit tanpa resolusi transitif,
        // supaya hanya wheel murni Python yang diunduh (tidak ada greenlet/Rust).
        pip {
            options("--no-deps")
            install("fastapi==0.115.0")
            install("starlette==0.38.6")
            install("pydantic==1.10.18")
            install("typing-extensions==4.12.2")
            install("anyio==4.6.2")
            install("exceptiongroup==1.2.2")
            install("idna==3.10")
            install("sniffio==1.3.1")
            install("uvicorn==0.30.6")
            install("click==8.1.7")
            install("h11==0.14.0")
            install("SQLAlchemy==2.0.36")
            install("httpx==0.27.2")
            install("httpcore==1.0.6")
            install("certifi==2024.8.30")
            install("python-multipart==0.0.9")
            install("python-dotenv==1.0.1")
        }
    }
}

tasks.named("preBuild") {
    dependsOn(packageBackend)
}

afterEvaluate {
    tasks.matching { it.name.startsWith("merge") && it.name.endsWith("Assets") }
        .configureEach { dependsOn(packageBackend) }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.9.2")
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    implementation("androidx.webkit:webkit:1.12.1")
    // T-06: backup harian harus tetap terjadwal tanpa WebView/thread Python.
    implementation("androidx.work:work-runtime-ktx:2.9.1")

    testImplementation("junit:junit:4.13.2")
}

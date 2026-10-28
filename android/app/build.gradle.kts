import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

/** One version for both the packaged runtime and the headers/libs Rust links against. */
val opencvVersion = "4.14.0"
val ndkVersionPinned = "28.2.13676358"
/** Android API level the Rust core is compiled for (= minSdk). */
val rustApi = 29

val rustAbis = (findProperty("easyscanner.abis") as String? ?: "arm64-v8a")
    .split(",").map { it.trim() }.filter { it.isNotEmpty() }
val abiTriples = mapOf(
    "arm64-v8a" to "aarch64-linux-android",
    "x86_64" to "x86_64-linux-android",
)

val localProps = Properties().apply {
    rootProject.file("local.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) }
}

android {
    namespace = "com.rawmechatronics.easyscanner"
    compileSdk = 36
    // Pinned so AGP does not download its own default build-tools version.
    buildToolsVersion = "36.1.0"
    ndkVersion = ndkVersionPinned

    defaultConfig {
        applicationId = "com.rawmechatronics.easyscanner"
        minSdk = rustApi
        targetSdk = 36
        versionCode = 3
        versionName = "0.2.1"
        ndk { abiFilters += rustAbis }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // installable for on-device performance runs without a release key
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
    }

    sourceSets["main"].jniLibs.srcDir(layout.buildDirectory.dir("rustJniLibs"))
}

/** The OpenCV AAR itself, for the headers and per-ABI .so the Rust core links to. */
val opencvAar: Configuration by configurations.creating

dependencies {
    implementation("org.opencv:opencv:$opencvVersion")
    opencvAar("org.opencv:opencv:$opencvVersion@aar")

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.2.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.preference:preference-ktx:1.2.1")

    testImplementation("junit:junit:4.13.2")
}

// ── Rust core (../core) ─────────────────────────────────────────────────────
// cargo builds libeasyscanner_core.so per ABI against OpenCV's prefab headers
// and libopencv_java4.so; the opencv crate generates its bindings with
// libclang at build time (see README → Toolchain).

val coreDir = rootProject.file("core")
val opencvPrefab = layout.buildDirectory.dir("opencv-prefab")

val extractOpenCvPrefab by tasks.registering(Copy::class) {
    from({ zipTree(opencvAar.singleFile) }) {
        include("prefab/modules/opencv_java4/**")
        eachFile { path = path.removePrefix("prefab/modules/opencv_java4/") }
        includeEmptyDirs = false
    }
    into(opencvPrefab)
}

fun hostTag(): String {
    val os = System.getProperty("os.name").lowercase()
    return when {
        os.contains("win") -> "windows-x86_64"
        os.contains("mac") -> "darwin-x86_64"
        else -> "linux-x86_64"
    }
}

val cargoTasks = rustAbis.map { abi ->
    val triple = abiTriples[abi] ?: error("no Rust target for ABI $abi")
    tasks.register<Exec>("cargoBuild-$abi") {
        group = "rust"
        description = "Build the Rust core for $abi"
        dependsOn(extractOpenCvPrefab)
        workingDir = coreDir
        inputs.files(fileTree(coreDir) {
            include("**/*.rs", "**/Cargo.toml", "Cargo.lock")
            exclude("target/**")
        })
        inputs.property("opencv", opencvVersion)
        outputs.file(coreDir.resolve("target/$triple/release/libeasyscanner_core.so"))
        commandLine("cargo", "build", "--release", "--target", triple, "-p", "easyscanner-core")
        doFirst {
            val ndk = androidComponents.sdkComponents.ndkDirectory.get().asFile
            val tc = ndk.resolve("toolchains/llvm/prebuilt/${hostTag()}")
            val win = hostTag().startsWith("windows")
            val exe = if (win) ".exe" else ""
            val clangTarget = "$triple$rustApi"
            val libclang = localProps.getProperty("libclang.dir") ?: System.getenv("LIBCLANG_PATH")
                ?: throw GradleException(
                    "libclang not found: set libclang.dir in local.properties or LIBCLANG_PATH (README → Toolchain)"
                )
            val prefab = opencvPrefab.get().asFile
            val envTriple = triple.replace('-', '_')
            val cargoTriple = envTriple.uppercase()
            // forward slashes: OPENCV_CLANG_ARGS is shell-split, backslashes would be escapes
            fun p(f: File) = f.absolutePath.replace('\\', '/')
            environment("CC_$envTriple", p(tc.resolve("bin/clang$exe")))
            environment("CXX_$envTriple", p(tc.resolve("bin/clang++$exe")))
            environment("AR_$envTriple", p(tc.resolve("bin/llvm-ar$exe")))
            environment("CFLAGS_$envTriple", "--target=$clangTarget")
            environment("CXXFLAGS_$envTriple", "--target=$clangTarget")
            environment("CARGO_TARGET_${cargoTriple}_LINKER", p(tc.resolve("bin/clang$exe")))
            environment("CARGO_TARGET_${cargoTriple}_RUSTFLAGS", "-C link-arg=--target=$clangTarget")
            // the binding generator asks this compiler for its system include
            // order; the NDK's target wrapper reports the Android one
            environment("CLANG_PATH", p(tc.resolve(if (win) "bin/$clangTarget-clang++.cmd" else "bin/$clangTarget-clang++")))
            environment("LIBCLANG_PATH", libclang)
            environment("OPENCV_INCLUDE_PATHS", p(prefab.resolve("include")))
            environment("OPENCV_LINK_PATHS", p(prefab.resolve("libs/android.$abi")))
            environment("OPENCV_LINK_LIBS", "opencv_java4")
            environment("OPENCV_DISABLE_PROBES", "pkg_config,cmake,vcpkg_cmake,vcpkg")
            environment(
                "OPENCV_CLANG_ARGS",
                "--target=$clangTarget --sysroot=${p(tc.resolve("sysroot"))} -resource-dir ${p(tc.resolve("lib/clang").listFiles()!!.first())}",
            )
        }
    }
}

val copyRustLibs by tasks.registering(Copy::class) {
    dependsOn(cargoTasks)
    rustAbis.forEach { abi ->
        from(coreDir.resolve("target/${abiTriples.getValue(abi)}/release/libeasyscanner_core.so")) { into(abi) }
    }
    into(layout.buildDirectory.dir("rustJniLibs"))
}

tasks.named("preBuild") { dependsOn(copyRustLibs) }

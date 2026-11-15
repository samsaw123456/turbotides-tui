plugins {
    kotlin("jvm") version "2.4.21"
    application
    id("org.jlleitschuh.gradle.ktlint") version "14.2.0"
}

group = "turbotides"
version = file("VERSION").readText().trim()
repositories { mavenCentral() }
dependencies {
    implementation("com.williamcallahan:tui4j:0.3.5")
    testImplementation(kotlin("test"))
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
kotlin { jvmToolchain(25) }
application { mainClass.set("turbotides.MainKt") }
tasks.test { useJUnitPlatform() }
tasks.register<Jar>("fatJar") {
    group = "build"
    archiveFileName.set("turbotides-tui.jar")
    manifest {
        attributes["Main-Class"] = application.mainClass.get()
        attributes["Enable-Native-Access"] = "ALL-UNNAMED"
    }
    duplicatesStrategy = DuplicatesStrategy.EXCLUDE
    from(sourceSets.main.get().output)
    dependsOn(configurations.runtimeClasspath)
    from({ configurations.runtimeClasspath.get().map { if (it.isDirectory) it else zipTree(it) } })
    exclude("META-INF/*.SF", "META-INF/*.RSA", "META-INF/*.DSA", "module-info.class")
}
tasks.named<JavaExec>("run") { standardInput = System.`in` }

tasks.processResources {
    inputs.property("gameVersion", project.version.toString())
    filesMatching("version.properties") { expand("gameVersion" to project.version.toString()) }
}

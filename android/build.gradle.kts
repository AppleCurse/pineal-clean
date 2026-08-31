plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.ksp) apply false
}

// Preserve the concrete Gradle cause in Actions job summaries even when a
// fail-closed quality task exits before producing its normal report.
gradle.buildFinished {
    val problem = failure ?: return@buildFinished
    val causes = generateSequence(problem as Throwable?) { it.cause }
        .mapIndexed { index, cause -> "${index + 1}. ${cause::class.qualifiedName}: ${cause.message}" }
        .joinToString("\n")
    val compilerLog = file("app/build/reports/kotlin-compiler-ci.log")
    val compilerErrors = if (compilerLog.exists()) {
        compilerLog.readLines()
            .filter { it.contains(" error:", ignoreCase = true) || it.trimStart().startsWith("e:") }
            .joinToString("\n")
    } else {
        ""
    }
    val details = listOf(causes, compilerErrors).filter { it.isNotBlank() }.joinToString("\n")
    val escaped = details
        .replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    println("::error title=Gradle failure::$escaped")
    System.getenv("GITHUB_STEP_SUMMARY")?.let { summaryPath ->
        file(summaryPath).appendText("\n## Gradle failure\n\n```text\n${details.take(60000)}\n```\n")
    }
}

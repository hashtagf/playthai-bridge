pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement { repositories { google(); mavenCentral() } }
rootProject.name = "PS5ThaiSubtitles"
include(":tv-overlay")
project(":tv-overlay").projectDir = file("apps/tv-overlay")

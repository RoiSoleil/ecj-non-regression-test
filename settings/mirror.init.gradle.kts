import java.net.URI
import org.gradle.api.Action
import org.gradle.api.Project
import org.gradle.api.artifacts.dsl.RepositoryHandler
import org.gradle.api.artifacts.repositories.MavenArtifactRepository
import org.gradle.api.initialization.Settings
import org.gradle.api.invocation.Gradle
import org.gradle.util.GradleVersion

val mirror = URI("https://maven-central.storage-download.googleapis.com/maven2/")
val central = Regex("https?://(repo\\.maven\\.apache\\.org|repo1\\.maven\\.org)/maven2/?")
val running = GradleVersion.current().baseVersion

fun reroute(repositories: RepositoryHandler) {
    repositories.withType(MavenArtifactRepository::class.java).configureEach(object : Action<MavenArtifactRepository> {
        override fun execute(repository: MavenArtifactRepository) {
            if (central.matches(repository.url.toString())) {
                repository.setUrl(mirror)
            }
        }
    })
}

if (running >= GradleVersion.version("6.0")) {
    Gradle::class.java.getMethod("beforeSettings", Action::class.java).invoke(gradle, object : Action<Settings> {
        override fun execute(settings: Settings) {
            settings.pluginManagement.repositories.maven(object : Action<MavenArtifactRepository> {
                override fun execute(repository: MavenArtifactRepository) {
                    repository.name = "googleMavenCentralMirror"
                    repository.setUrl(mirror)
                }
            })
            settings.pluginManagement.repositories.gradlePluginPortal()
            reroute(settings.pluginManagement.repositories)
            reroute(settings.buildscript.repositories)
            if (running >= GradleVersion.version("6.8")) {
                val management = Settings::class.java.getMethod("getDependencyResolutionManagement")
                reroute(management.returnType.getMethod("getRepositories").invoke(management.invoke(settings)) as RepositoryHandler)
            }
        }
    })
    allprojects(object : Action<Project> {
        override fun execute(project: Project) {
            reroute(project.buildscript.repositories)
            reroute(project.repositories)
        }
    })
}

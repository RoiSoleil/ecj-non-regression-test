val merapiJavac: String? = System.getenv("MERAPI_JAVAC")
if (!merapiJavac.isNullOrEmpty()) {
    allprojects {
        tasks.withType<JavaCompile>().configureEach {
            options.isFork = true
            options.forkOptions.executable = merapiJavac
        }
    }
}
